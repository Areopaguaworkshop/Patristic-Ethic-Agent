"""Deterministic policy layer (plan §5.4): signals, matching, disposition.

Stdlib only at runtime; no I/O except load_policy. The disposition
precedence in evaluate_policy is FROZEN — see the numbered rules there.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pydantic only needed for typing; policy logic is stdlib
    from .interpreter import Observation

Disposition = Literal["allow", "guide", "refuse", "clarify", "review"]
SourceStatus = Literal["verified", "partial", "missing"]

# Documented lexical marker lists. Lowercased substring match against
# observation.requested_assistance and observation.expressed_intent.
FACILITATION_MARKERS: tuple[str, ...] = (
    "give me the dose",
    "tell me the method",
    "how many",
    "help me plan",
    "make it happen",
    "make it more persuasive",
    "write a plan",
    "draft a post",
    "recruit",
    "untraceable",
    "operational",
    "without getting caught",
    "get them alone",
    "beat him",
    "hurt him",
    "sabotage",
    "poison",
)

DISTRESS_MARKERS: tuple[str, ...] = (
    "don't want to keep living",
    "do not want to keep living",
    "better off dead",
    "kill myself",
    "end it all",
    "suicide",
    "self-harm",
    "no reason to live",
    "can't go on",
    "cant go on",
)

AMBIGUITY_WORDS: tuple[str, ...] = ("unclear", "ambiguous", "unknown")

# Emergency lexical candidate markers (plan §6.3): principle id -> terms.
# Used ONLY when the structured interpreter produced no topics. This is a
# tested fallback for degraded/fake backends, never the intention detector.
# Known ceiling: prevention/analysis phrasing can be flagged (e.g. security
# briefings about recruitment); evaluation must use the interpreter path.
LEXICAL_MARKERS: dict[str, tuple[str, ...]] = {
    "PEA-P01": (
        "kill", "murder", "poison", "put him to sleep", "put her to sleep",
        "end it all", "unalive", "dose", "overdose", "sleeping pills",
        "untraceable", "make it look accidental", "beat him", "beat her",
        "hurt him badly", "weapon", "attack",
    ),
    "PEA-P02": (
        "rape", "have sex with someone who has clearly said no",
        "force himself", "force herself", "child abuse", "molest", "sex slave",
    ),
    "PEA-P03": (
        "recruit", "draft a post", "join the brothers", "join our cell",
        "fighters", "go operational", "checkpoint", "clearly a device",
        "bomb", "explosives",
    ),
    "PEA-P04": (
        "phishing", "fake transfer", "embezzle", "steal", "fraud",
        "sabotage", "without getting caught",
    ),
    "PEA-P05": ("perjury", "lie on my resume", "false testimony"),
    "PEA-P06": ("witch", "curse", "ritual", "occult"),
    "PEA-P08": ("furious", "rage", "hurt him", "revenge", "regret it"),
    "PEA-P09": ("sabotage", "envy", "jealous", "resent"),
    "PEA-P10": ("drunk", "drink most nights", "alcohol", "orgies"),
}

# Documented benign guards: if any appears, the emergency fallback returns
# no candidates (technical usage, teaching/quotation contexts). Guarding
# deliberately aggressive to avoid emergency false positives; the
# interpreter path remains the primary detector.
BENIGN_GUARDS: tuple[str, ...] = (
    "kill a process", "kill the process", "kill processes",
    "killed a process", "kill -9", "daemon", "server process",
    "process id", "pid=", "docker",
    "for a class", "essay", "sunday school", "quotation", "history class",
)


def lexical_candidates(text: str) -> list[str]:
    """Emergency lexical candidate generation over raw request text.

    Returns principle ids whose documented markers appear in ``text``,
    first-seen order, deduplicated. Returns [] when a documented benign
    guard matches (technical/teaching contexts). Callers use this ONLY
    when the interpreter supplied no topics — see module docstring notes
    about its known false-positive ceiling.
    """
    lowered = text.lower()
    if any(g in lowered for g in BENIGN_GUARDS):
        return []
    out: list[str] = []
    for pid, markers in LEXICAL_MARKERS.items():
        if any(m in lowered for m in markers) and pid not in out:
            out.append(pid)
    return out


def merge_lexical_matches(
    matched: list[PrincipleRef], candidate_ids: list[str], policy_doc: dict
) -> list[PrincipleRef]:
    """Add lexical-fallback PrincipleRefs (dedup by id, non-overridable first)."""
    by_id = {p["id"]: p for p in policy_doc.get("principles", [])}
    refs = {r.id: r for r in matched}
    for pid in candidate_ids:
        p = by_id.get(pid)
        if p is None or pid in refs:
            continue
        refs[pid] = PrincipleRef(
            id=pid,
            title=p.get("title", pid),
            non_overridable=bool(p.get("non_overridable", False)),
            matched_via=f"lexical:{pid}",
        )
    return sorted(refs.values(), key=lambda r: not r.non_overridable)


def augment_signals_from_text(signals: Signals, text: str) -> Signals:
    """Emergency fallback: derive facilitation/distress from raw text when
    the interpreter supplied no topics (degraded/fake backend)."""
    lowered = text.lower()
    facilitation = signals.facilitation or any(
        m in lowered for m in FACILITATION_MARKERS
    )
    distress = signals.distress or any(m in lowered for m in DISTRESS_MARKERS)
    benign = signals.benign and not facilitation
    return Signals(
        facilitation=facilitation,
        distress=distress,
        ambiguity=signals.ambiguity,
        benign=benign,
        urgent_care=signals.urgent_care,
    )


@dataclass
class Signals:
    """Derived risk flags for one Observation.

    urgent_care is an upstream channel (e.g. host-detected crisis);
    derive_signals leaves it False.
    """

    facilitation: bool
    distress: bool
    ambiguity: bool
    benign: bool
    urgent_care: bool = False


@dataclass
class PrincipleRef:
    """A matched principle, with how the match was made."""

    id: str
    title: str
    non_overridable: bool
    matched_via: str


@dataclass
class Decision:
    """The policy layer's verdict for one Observation."""

    disposition: Disposition
    principle_ids: list[str] = field(default_factory=list)
    reason: str = ""
    message_evidence: list[str] = field(default_factory=list)
    source_status: SourceStatus = "verified"
    urgent_care: bool = False
    non_overridable: bool = False
    policy_version: str = ""


def derive_signals(observation: "Observation") -> Signals:
    """Lexical fallback signal derivation.

    This lexical layer is a tested fallback; the interpreter's
    structured topics/intent drive the primary path in assess.
    Markers are lowercased substring matches over
    requested_assistance and expressed_intent.
    """
    req = observation.requested_assistance.lower()
    intent = observation.expressed_intent.lower()
    if observation.assistance_type == "facilitation":
        facilitation = True
    elif observation.assistance_type in ("benign_discussion", "support_seeking"):
        facilitation = False
    else:
        facilitation = any(m in req or m in intent for m in FACILITATION_MARKERS)
    distress = any(m in req or m in intent for m in DISTRESS_MARKERS)
    ambiguity = bool(observation.unresolved_ambiguity) or any(
        w in intent for w in AMBIGUITY_WORDS
    )
    benign = bool(observation.benign_explanations) and not facilitation
    return Signals(facilitation, distress, ambiguity, benign)


def load_policy(path) -> dict:
    """Load a policy document from a JSON file with clear errors."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"policy file not found: {path}") from None
    except json.JSONDecodeError as e:
        raise ValueError(f"policy file {path} is not valid JSON: {e}") from e


def match_principles(observation: "Observation", policy_doc: dict) -> list[PrincipleRef]:
    """Match observation topics/request text against principle terms.

    Case-insensitive substring match: any observation topic against
    principle topics or euphemisms (either direction), plus principle
    topics directly inside requested_assistance. Deduplicates by id;
    non-overridable principles sort first.
    """
    req = observation.requested_assistance.lower()
    obs_topics = [t.lower() for t in observation.topics]
    refs: dict[str, PrincipleRef] = {}
    for p in policy_doc.get("principles", []):
        for term, kind in [
            *[(t, "topic") for t in p.get("topics", [])],
            *[(e, "euphemism") for e in p.get("euphemisms", [])],
        ]:
            tl = term.lower()
            if any(tl in t or t in tl for t in obs_topics):
                via = f"{kind}:{term}"
            elif kind == "topic" and tl in req:
                via = f"request:{term}"
            else:
                continue
            refs.setdefault(
                p["id"],
                PrincipleRef(
                    id=p["id"],
                    title=p.get("title", p["id"]),
                    non_overridable=bool(p.get("non_overridable", False)),
                    matched_via=via,
                ),
            )
    return sorted(refs.values(), key=lambda r: not r.non_overridable)


def evaluate_policy(
    observation: "Observation",
    *,
    matched: list[PrincipleRef],
    signals: Signals,
    source_status: SourceStatus,
    policy_version: str,
) -> Decision:
    """Apply the FROZEN disposition precedence (test each rule):

    1. matched non-overridable principle AND facilitation -> refuse
       (never releasable; urgent_care stays False).
    2. ambiguity AND (non-overridable matched OR confidence is
       None) -> review.
    3. ambiguity -> clarify.
    4. distress -> guide with urgent_care=True.
    5. any matched principle -> guide.
    6. otherwise -> allow.

    Invariants: source_status is recorded, never consulted — a
    missing source can never turn a refuse into an allow.
    """
    evidence = [e.source_id for e in observation.evidence]
    ids = [p.id for p in matched]
    non_over = [p for p in matched if p.non_overridable]

    if non_over and signals.facilitation:
        return Decision(
            disposition="refuse",
            principle_ids=ids,
            reason="non-overridable principle matched and the request facilitates harm",
            message_evidence=evidence,
            source_status=source_status,
            urgent_care=False,
            non_overridable=True,
            policy_version=policy_version,
        )
    if signals.ambiguity and (non_over or observation.confidence is None):
        return Decision(
            disposition="review",
            principle_ids=ids,
            reason="ambiguous request with a non-overridable match or missing confidence",
            message_evidence=evidence,
            source_status=source_status,
            policy_version=policy_version,
        )
    if signals.ambiguity:
        return Decision(
            disposition="clarify",
            principle_ids=ids,
            reason="ambiguous request needs clarification before proceeding",
            message_evidence=evidence,
            source_status=source_status,
            policy_version=policy_version,
        )
    if signals.distress:
        return Decision(
            disposition="guide",
            principle_ids=ids,
            reason="user distress: respond with care",
            message_evidence=evidence,
            source_status=source_status,
            urgent_care=True,
            policy_version=policy_version,
        )
    if matched:
        return Decision(
            disposition="guide",
            principle_ids=ids,
            reason="matched principles guide the response",
            message_evidence=evidence,
            source_status=source_status,
            policy_version=policy_version,
        )
    return Decision(
        disposition="allow",
        principle_ids=ids,
        reason="no principle matched and no risk signals raised",
        message_evidence=evidence,
        source_status=source_status,
        policy_version=policy_version,
    )
