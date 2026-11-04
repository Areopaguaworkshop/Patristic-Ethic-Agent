"""Assessment core (plan §5.2–5.4): envelope -> decision -> guidance.

Pipeline: interpret (stage-aware, never mutating the envelope) ->
derive signals + match principles -> retrieve citations by topic ->
evaluate policy (FROZEN precedence) -> compose guidance -> verify
citations -> structural output check on refused candidates.

Invariants:
- A missing/failed corpus or interpreter is an operational fact, never a
  moral conclusion: a clear harmful request stays refused.
- Interpreter unavailability withholds unreviewed output (stage=output)
  or asks to clarify (input/pre_action), with a non-accusatory message.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from . import corpus, guidance, policy
from .interpreter import Evidence, InterpreterFailure, InterpreterUnavailable, Observation

if TYPE_CHECKING:
    from .context import ContextEnvelope
    from .guidance import GuidanceResult
    from .interpreter import InterpreterFailure
    from .policy import Decision

Action = Literal["proceed", "guide", "refuse", "clarify", "review", "withhold"]

_ACTION_FOR_DISPOSITION: dict = {
    "allow": "proceed",
    "guide": "guide",
    "refuse": "refuse",
    "clarify": "clarify",
    "review": "review",
}

_WITHHELD_MESSAGE = (
    "PEA could not complete its review; this response was withheld. "
    "No judgment about the user is implied."
)


@dataclass
class AssessResult:
    action: Action
    decision: "Decision | None" = None
    guidance: "GuidanceResult | None" = None
    failure: "InterpreterFailure | None" = None
    audit: dict = field(default_factory=dict)


def _stage_request(envelope: "ContextEnvelope") -> str:
    """The original user request; action/output are separate trusted fields."""
    return envelope.request


def _validate_observation_evidence(obs, envelope: "ContextEnvelope") -> None:
    """Reject model evidence that is not an exact quote from supplied context."""
    sources = {"current_request": envelope.request}
    if envelope.candidate_response is not None:
        sources["candidate_response"] = envelope.candidate_response
    if envelope.proposed_action is not None:
        action = envelope.proposed_action
        sources["proposed_action"] = (
            f"{action.tool} "
            f"{json.dumps(action.arguments, sort_keys=True, ensure_ascii=False)}"
        )
    for message in envelope.messages:
        sources[message.source_id] = message.text
    for excerpt in envelope.earlier_excerpts:
        sources[excerpt.source_id] = excerpt.text
    if envelope.summary is not None:
        sources[envelope.summary.source_id] = envelope.summary.text

    if (obs.topics or obs.assistance_type != "uncertain") and not obs.evidence:
        raise ValueError("structured judgment has no source evidence")
    for evidence in obs.evidence:
        source = sources.get(evidence.source_id)
        if source is None or not evidence.quote.strip():
            raise ValueError(f"evidence source is missing: {evidence.source_id}")
        if " ".join(evidence.quote.split()) not in " ".join(source.split()):
            raise ValueError(f"evidence quote does not match source: {evidence.source_id}")


def _default_verify(db_path, units: list):
    """Whitespace-collapsed exact substring against the retrieved unit's
    stored text for the same unit_id (mirrors corpus.verify_quote without
    a second db hit)."""
    by_id = {u.id: u.text for u in units if u.text}

    def verify(unit_id: str, quote: str) -> bool:
        text = by_id.get(unit_id)
        if text is None:
            return False
        return " ".join(quote.split()) in " ".join(text.split())

    return verify


def _retrieve(db_path, topics: list[str]) -> tuple[list, str]:
    """Search per topic (FTS5). Missing file -> no units, "missing", no crash.
    Any search error with some units found -> "partial"."""
    if db_path is None or not Path(db_path).exists():
        return [], "missing"
    units: list = []
    seen: set[str] = set()
    errors = 0
    for topic in topics[:8]:
        try:
            # ponytail: quote each term; hyphenated topics like "self-harm"
            # are FTS5 syntax errors unquoted. Internal quotes need doubling.
            quoted = '"' + topic.replace('"', '""') + '"'
            hits = corpus.search_passages(db_path, quoted, limit=5)
            for u in hits:
                if u.id not in seen:
                    seen.add(u.id)
                    units.append(u)
        except Exception:
            errors += 1
    if not units:
        return [], "missing"  # type: ignore[return-value]
    return units, ("partial" if errors else "verified")  # type: ignore[return-value]


def _withheld_guidance() -> "GuidanceResult":
    return guidance.GuidanceResult(
        text=_WITHHELD_MESSAGE,
        citations=[],
        source_status="missing",
        limited=True,
    )


def _safety_text(envelope: "ContextEnvelope") -> str:
    """Request plus the action or candidate that the fallback must inspect."""
    text = envelope.request
    if envelope.proposed_action is not None:
        text += (
            "\nTool: " + envelope.proposed_action.tool
            + " Arguments: " + json.dumps(
                envelope.proposed_action.arguments, sort_keys=True, ensure_ascii=False
            )
        )
    if envelope.candidate_response:
        text += "\nCandidate: " + envelope.candidate_response
    return text


def _non_overridable_safety(staged, policy_doc: dict, db_path):
    """Refuse explicit P01-P03 harm without depending on the model.

    This is the emergency lexical path for the gravest principles. It runs
    before the interpreter, so an interpreter outage cannot turn a clear
    harmful request into a mere clarification. A proposed tool action is
    treated as facilitation because the action itself is the request.
    """
    if staged.stage not in ("input", "pre_action"):
        return None
    text = _safety_text(staged)
    safety = policy.explicit_harm_candidates(text)
    if not safety:
        return None
    signals = policy.augment_signals_from_text(
        policy.Signals(facilitation=False, distress=False, ambiguity=False, benign=False),
        text,
    )
    if staged.stage == "pre_action" or any(
        marker in text.lower() for marker in policy.REQUEST_MARKERS
    ):
        signals = replace(signals, facilitation=True)
    elif not signals.facilitation:
        return None
    matched = policy.merge_lexical_matches([], safety, policy_doc)
    topics = list(safety)
    for principle in policy_doc.get("principles", []):
        if principle["id"] in safety:
            topics.extend(principle.get("topics", []))
    units, source_status = _retrieve(db_path, topics)
    observation = Observation(
        requested_assistance=text,
        assistance_type="facilitation",
        affected_parties=[],
        topics=topics,
        expressed_intent="explicit harmful request",
        evidence=[Evidence(source_id="current_request", quote=text)],
        benign_explanations=[],
        unresolved_ambiguity=[],
        confidence=1.0,
    )
    decision = policy.evaluate_policy(
        observation,
        matched=matched,
        signals=signals,
        source_status=source_status,  # type: ignore[arg-type]
        policy_version=policy_doc.get("policy_version", ""),
    )
    descriptions = {
        p["id"]: f"{p['id']} {p.get('title', p['id'])}"
        for p in policy_doc.get("principles", [])
    }
    result = guidance.compose_guidance(
        decision, passages=units, principle_descriptions=descriptions
    )
    result.citations = guidance.filter_verified(
        result.citations, _default_verify(db_path, units)
    )
    if units and not result.citations:
        result = guidance.compose_guidance(
            decision, passages=[], principle_descriptions=descriptions
        )
    action = _ACTION_FOR_DISPOSITION.get(decision.disposition, "withhold")
    return decision, result, action


def assess(
    envelope: "ContextEnvelope",
    *,
    interpreter,
    policy_doc: dict,
    db_path,
    corpus_version: str = "0.1.0-draft",
    verify_fn=None,
) -> AssessResult:
    start = time.perf_counter()
    audit: dict = {
        "event_id": envelope.turn.event_id or envelope.turn.id,
        "session_id": envelope.session.id,
        "stage": envelope.stage,
        "policy_version": policy_doc.get("policy_version", ""),
        "corpus_version": corpus_version,
    }
    policy_problems = policy.validate_policy_doc(policy_doc)
    if policy_problems:
        failure = InterpreterFailure(
            reason="invalid policy document",
            detail="; ".join(policy_problems),
            kind="schema",
        )
        return _finish(
            "withhold", None, _withheld_guidance(), failure, audit, start, None
        )

    decision = None
    guidance_result = None
    failure = None
    output_check_problems = None

    try:
        staged = envelope.model_copy(deep=True)
        staged.request = _stage_request(envelope)
        safety = _non_overridable_safety(staged, policy_doc, db_path)
        if safety is not None:
            decision, guidance_result, action = safety
            return _finish(action, decision, guidance_result, None, audit, start, None)
        obs = interpreter.interpret(staged)
        _validate_observation_evidence(obs, envelope)
    except InterpreterUnavailable as e:
        failure = e.failure
        action = "withhold" if envelope.stage == "output" else "clarify"
        guidance_result = _withheld_guidance()
        return _finish(
            action, decision, guidance_result, failure, audit, start, output_check_problems
        )
    except (TypeError, ValueError) as e:
        failure = InterpreterFailure(
            reason="interpreter evidence failed validation",
            detail=str(e),
            kind="schema",
        )
        action = "withhold" if envelope.stage == "output" else "clarify"
        guidance_result = _withheld_guidance()
        return _finish(
            action, decision, guidance_result, failure, audit, start, output_check_problems
        )

    signals = policy.derive_signals(obs)
    matched = policy.match_principles(obs, policy_doc)
    # Emergency lexical fallback (plan §6.3): the full candidate set runs
    # only when the interpreter produced no topics. The hard P01-P03 set is
    # always merged, and the text includes proposed tool arguments or the
    # output candidate, so a model that returns unrelated topics cannot hide
    # an explicit harmful request.
    lexical_text = _safety_text(staged)
    hard = policy.explicit_harm_candidates(lexical_text)
    if hard:
        matched = policy.merge_lexical_matches(matched, hard, policy_doc)
    candidates = policy.lexical_candidates(lexical_text)
    if not obs.topics:
        if candidates:
            matched = policy.merge_lexical_matches(matched, candidates, policy_doc)
        signals = policy.augment_signals_from_text(signals, lexical_text)
        if hard and staged.stage == "pre_action":
            signals = replace(signals, facilitation=True)

    topics = list(obs.topics)
    for p in policy_doc.get("principles", []):
        if p["id"] in {m.id for m in matched}:
            topics.extend(p.get("topics", []))
    units, source_status = _retrieve(db_path, topics)

    decision = policy.evaluate_policy(
        obs,
        matched=matched,
        signals=signals,
        source_status=source_status,  # type: ignore[arg-type]  # runtime value is a valid SourceStatus
        policy_version=policy_doc.get("policy_version", ""),
    )

    descriptions = {
        p["id"]: f"{p['id']} {p.get('title', p['id'])}"
        for p in policy_doc.get("principles", [])
    }
    guidance_result = guidance.compose_guidance(
        decision, passages=units, principle_descriptions=descriptions
    )
    verifier = verify_fn or _default_verify(db_path, units)
    guidance_result.citations = guidance.filter_verified(
        guidance_result.citations, verifier
    )
    if units and not guidance_result.citations:
        guidance_result = guidance.compose_guidance(
            decision, passages=[], principle_descriptions=descriptions
        )

    if envelope.stage == "output":
        candidate = envelope.candidate_response or ""
        check = guidance.assess_output(candidate, decision, units)
        citation_problem = any(
            problem in ("unsupported_quote", "missing_citation")
            for problem in check.problems
        )
        if check.problems:
            output_check_problems = check.problems
        if citation_problem and decision.disposition != "refuse":
            guidance_result = _withheld_guidance()
            action = "withhold"
        else:
            action = _ACTION_FOR_DISPOSITION.get(decision.disposition, "withhold")
    else:
        action = _ACTION_FOR_DISPOSITION.get(decision.disposition, "withhold")

    return _finish(
        action, decision, guidance_result, failure, audit, start, output_check_problems
    )


def _finish(
    action: Action,
    decision,
    guidance_result,
    failure,
    audit: dict,
    start: float,
    output_check_problems,
) -> AssessResult:
    audit["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
    if output_check_problems is not None:
        audit["output_check"] = output_check_problems
    return AssessResult(
        action=action,
        decision=decision,
        guidance=guidance_result,
        failure=failure,
        audit=audit,
    )
