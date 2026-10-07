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
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from . import corpus, guidance, policy
from .interpreter import InterpreterUnavailable

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
    """Request text for the stage, building a copy — envelope untouched."""
    text = envelope.request
    if envelope.stage == "pre_action" and envelope.proposed_action is not None:
        text += "\nProposed action: " + json.dumps(
            {
                "tool": envelope.proposed_action.tool,
                "arguments": envelope.proposed_action.arguments,
            }
        )
    elif envelope.stage == "output" and envelope.candidate_response is not None:
        text += "\nCandidate response: " + envelope.candidate_response
    return text


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
            # are FTS5 syntax errors unquoted.
            hits = corpus.search_passages(db_path, f'"{topic}"', limit=5)
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
    decision = None
    guidance_result = None
    failure = None
    output_check_problems = None

    try:
        staged = envelope.model_copy(deep=True)
        staged.request = _stage_request(envelope)
        obs = interpreter.interpret(staged)
    except InterpreterUnavailable as e:
        failure = e.failure
        action = "withhold" if envelope.stage == "output" else "clarify"
        guidance_result = _withheld_guidance()
        return _finish(
            action, decision, guidance_result, failure, audit, start, output_check_problems
        )

    signals = policy.derive_signals(obs)
    matched = policy.match_principles(obs, policy_doc)
    # Emergency lexical fallback (plan §6.3): only when the interpreter
    # produced no topics (degraded/fake backend). Candidate generation,
    # never the primary path; benign guards suppress technical/teaching
    # contexts. Documented ceiling: prevention phrasing can false-positive.
    if not obs.topics:
        candidates = policy.lexical_candidates(staged.request)
        if candidates:
            matched = policy.merge_lexical_matches(matched, candidates, policy_doc)
        # Distress/facilitation signals also come from raw text when the
        # interpreter supplied no topics (e.g. distress with no principle
        # marker), so augment regardless of candidate matches.
        signals = policy.augment_signals_from_text(signals, staged.request)

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

    if envelope.stage == "output" and decision.disposition == "refuse":
        candidate = envelope.candidate_response or ""
        check = guidance.assess_output(candidate, decision, units)
        if not check.ok:
            revised, used = guidance.revise_once(
                candidate, check, lambda text, problems: None
            )
            # ponytail: revise_fn returns None by design -> fall back to the
            # composed refuse guidance; the candidate is never released.
            guidance_result = guidance.compose_guidance(
                decision,
                passages=units,
                principle_descriptions=descriptions,
            )
            output_check_problems = check.problems

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