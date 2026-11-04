"""Deterministic policy layer (plan §5.4): signals, matching, disposition.

Stdlib only at runtime; no I/O except load_policy. The disposition
precedence in evaluate_policy is FROZEN — see the numbered rules there.
"""

from __future__ import annotations

import json
import re
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

PRINCIPLE_IDS = {f"PEA-P{i:02d}" for i in range(1, 11)}
NON_OVERRIDABLE_IDS = {"PEA-P01", "PEA-P02", "PEA-P03"}

# A hard P01-P03 phrase plus one of these is a request for assistance, even
# when no general facilitation marker appears. The model path remains primary;
# this keeps the emergency screen from downgrading a direct request to advice.
REQUEST_MARKERS: tuple[str, ...] = (
    "tell me how", "explain how", "show me how", "how do i", "how can i",
    "help me", "give me", "what is the best way", "i need to", "i want to",
)

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
    "PEA-P10": (
        "drunk", "drink most nights", "alcohol", "orgies", "gambling",
        "betting", "casino", "compulsive scrolling", "can't stop scrolling",
        "gaming addiction",
    ),
}

# Documented benign guards: if any appears, the emergency fallback returns
# no candidates (technical usage, teaching/quotation contexts). Guarding
# deliberately aggressive to avoid emergency false positives; the
# interpreter path remains the primary detector.
BENIGN_GUARDS: tuple[str, ...] = (
    "kill a process", "kill the process", "kill processes",
    "killed a process", "kill my process", "kill my own process",
    "kill my server", "kill my app", "kill my daemon", "kill my container",
    "kill -9", "daemon", "server process",
    "process id", "pid=", "docker",
    "for a class", "essay", "sunday school", "quotation", "history class",
)

# A direct technical target is the only benign use of "kill my". A mixed
# message with any non-technical target still reaches the hard screen.
_TECHNICAL_KILL_MY = re.compile(
    r"\bkill my (?:own )?(?:process(?:es)?|server(?:s)?|daemon(?:s)?|"
    r"container(?:s)?|pod(?:s)?|job(?:s)?|task(?:s)?|program(?:s)?|"
    r"script(?:s)?|session(?:s)?|terminal(?:s)?|browser(?:s)?|"
    r"app(?:lication)?s?|service(?:s)?|thread(?:s)?|worker(?:s)?)\b"
)


def _only_technical_kill_my(lowered: str) -> bool:
    starts = [m.start() for m in re.finditer(r"\bkill my\b", lowered)]
    return bool(starts) and all(_TECHNICAL_KILL_MY.match(lowered, start) for start in starts)


EXPLICIT_HARM_MARKERS: dict[str, tuple[str, ...]] = {
    "PEA-P01": (
        "kill my", "murder my", "poison my", "shoot my", "stab my",
        "kill him", "kill her", "beat him", "beat her", "dose of poison",
    ),
    "PEA-P02": ("rape", "force my", "sex slave"),
    "PEA-P03": (
        "recruit fighters", "join our cell", "go operational",
        "build a bomb", "make a bomb",
    ),
}


def explicit_harm_candidates(text: str) -> list[str]:
    """High-confidence P01-P03 phrases, used before any model call.

    This is the non-overridable path, so a global benign guard must never
    suppress it. The only exception is a technical "kill my <process>" phrase
    whose every occurrence has a technical object.
    """
    lowered = text.lower()
    out: list[str] = []
    for pid, markers in EXPLICIT_HARM_MARKERS.items():
        for marker in markers:
            if marker not in lowered:
                continue
            if marker == "kill my" and _only_technical_kill_my(lowered):
                continue
            out.append(pid)
            break
    return out


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


def validate_policy_doc(doc: dict) -> list[str]:
    """Return structural problems for a policy document; empty means usable.

    The runtime is fail-closed: a policy with missing or incomplete principles
    must not be accepted, because an empty principle list would allow every
    request.
    """
    problems: list[str] = []
    if not isinstance(doc, dict):
        return ["policy must be a JSON object"]
    if doc.get("schema_version") != "1.0":
        problems.append("schema_version must be '1.0'")
    version = doc.get("policy_version")
    if not isinstance(version, str) or not version.strip():
        problems.append("policy_version must be a non-empty string")
    if doc.get("review_status") not in {"draft-unreviewed", "reviewed"}:
        problems.append("review_status must be draft-unreviewed or reviewed")
    principles = doc.get("principles")
    if not isinstance(principles, list):
        return problems + ["principles must be a list"]
    ids: list[str] = []
    for index, principle in enumerate(principles):
        label = f"principles[{index}]"
        if not isinstance(principle, dict):
            problems.append(f"{label} must be an object")
            continue
        pid = principle.get("id")
        if not isinstance(pid, str) or not pid.strip():
            problems.append(f"{label} is missing id")
            continue
        ids.append(pid)
        if not isinstance(principle.get("title"), str) or not principle["title"].strip():
            problems.append(f"{pid} is missing title")
        topics = principle.get("topics")
        if not isinstance(topics, list) or not topics:
            problems.append(f"{pid} must have a non-empty topics list")
        if not isinstance(principle.get("non_overridable"), bool):
            problems.append(f"{pid} must declare boolean non_overridable")
        if pid in NON_OVERRIDABLE_IDS and principle.get("non_overridable") is not True:
            problems.append(f"{pid} must be non-overridable")
    if len(ids) != len(set(ids)):
        problems.append("policy contains duplicate principle ids")
    missing = sorted(PRINCIPLE_IDS - set(ids))
    unexpected = sorted(set(ids) - PRINCIPLE_IDS)
    if missing:
        problems.append("policy is missing principles: " + ", ".join(missing))
    if unexpected:
        problems.append("policy has unknown principles: " + ", ".join(unexpected))
    return problems


def load_policy(path) -> dict:
    """Load and structurally validate a policy document with clear errors."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"policy file not found: {path}") from None
    except json.JSONDecodeError as e:
        raise ValueError(f"policy file {path} is not valid JSON: {e}") from e
    problems = validate_policy_doc(doc)
    if problems:
        raise ValueError(f"policy file {path} is invalid: " + "; ".join(problems))
    return doc


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
