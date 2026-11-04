"""Guidance composition per the response pattern (plan §5.4).

Pure text composition: build citations from passages (no I/O, no db here
— the caller verifies with corpus.verify_quote via `filter_verified`).

Pattern: acknowledge -> boundary/principle -> constructive next step ->
citations. Distress: gentle care + human help, no shame. No fabrication;
retrieval failure = "insufficient evidence in this collection" (never
"the Fathers were silent").

Decision duck-typed: anything with disposition/principle_ids/urgent_care/
source_status attributes works (no runtime policy import).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # duck-typed at runtime; no file-order dependency
    from patristic_ethics.policy import Decision


# Heuristic marker list for operational harmful-assistance content on a
# refuse disposition. Cheap substring check, deliberately conservative
# toward recall; the interpreter/assess layer is the primary gate.
DEFAULT_PROHIBITED_MARKERS: tuple[str, ...] = (
    "dose",
    "method to",
    "step 1",
    "instructions",
    "how to make",
    "recipe",
    "untraceable",
)

_MISSING_CLAUSE = "insufficient evidence in this collection"
_KNOWN_SOURCE = re.compile(
    r"\b(?:scripture|the bible|the fathers|st\.?\s*)?(?:"
    r"Augustine|Basil(?: the Great)?|Gregory (?:of Nyssa|Nazianzen|the Great)|"
    r"John Chrysostom|Chrysostom|Jerome|Athanasius|Clement of Alexandria|"
    r"Irenaeus|Cyprian|Ambrose|Origen|the Gospel|Matthew|Mark|Luke|John|Romans)\b",
    re.IGNORECASE,
)


@dataclass
class Citation:
    """One citable passage render (provenance + verbatim text)."""

    unit_id: str
    author: str
    work: str
    locus: str | None
    source_url: str
    quote: str
    language: str
    rights_status: str
    review_status: str = "unknown"
    source_class: str = "patristic"


@dataclass
class GuidanceResult:
    """Composed guidance plus its provenance and transparency state."""

    text: str
    citations: list[Citation] = field(default_factory=list)
    source_status: str = "verified"
    limited: bool = False


@dataclass
class OutputCheck:
    """Structural self-check of a candidate output before release."""

    ok: bool
    problems: list[str] = field(default_factory=list)


def _attr(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name) if obj is not None and hasattr(obj, name) else default


def _collapse_ws(s: str) -> str:
    return " ".join(s.split())


def _principle_labels(decision: Any, descriptions: dict[str, str] | None) -> list[str]:
    ids = _attr(decision, "principle_ids", []) or []
    labels = []
    for pid in ids:
        if descriptions and pid in descriptions:
            labels.append(f"{pid} ({descriptions[pid]})")
        else:
            labels.append(pid)
    return labels


def _citations_from(passages: list[Any]) -> list[Citation]:
    """Structural citations: passages with text (null text skipped)."""
    out = []
    for p in passages or []:
        text = _attr(p, "text")
        if not text:
            continue
        out.append(
            Citation(
                unit_id=_attr(p, "id", ""),
                author=_attr(p, "author", ""),
                work=_attr(p, "work", ""),
                locus=_attr(p, "locus"),
                source_url=_attr(p, "source_url", ""),
                quote=text,
                language=_attr(p, "language", ""),
                rights_status=_attr(p, "rights_status", ""),
                review_status=_attr(p, "review_status", "unknown"),
                source_class=_attr(p, "source_class", "patristic"),
            )
        )
    return out


def filter_verified(
    citations: list[Citation], verify_fn: Callable[[str, str], bool]
) -> list[Citation]:
    """Drop citations whose quote fails verify_fn(unit_id, quote).

    Caller binds verify_fn to the db, e.g.
    functools.partial(corpus.verify_quote, db_path) — keeps this pure.
    """
    return [c for c in citations if verify_fn(c.unit_id, c.quote)]


def compose_guidance(
    decision: Any,
    *,
    passages: list[Any],
    envelope: Any = None,  # ponytail: reserved, host envelope unused here
    principle_descriptions: dict[str, str] | None = None,
) -> GuidanceResult:
    """Compose response-pattern text for the disposition. Pure: no I/O."""
    disposition = _attr(decision, "disposition", "")
    urgent = bool(_attr(decision, "urgent_care", False))
    decision_missing = _attr(decision, "source_status") == "missing"
    labels = _principle_labels(decision, principle_descriptions)
    descriptions = principle_descriptions or {}
    citations = _citations_from(passages)
    verified = bool(citations)
    limited = decision_missing or not verified

    parts: list[str] = []
    if disposition == "refuse":
        parts.append("I hear the request.")
        if labels:
            parts.append(
                "That falls outside what I can help with, on the principle of "
                + " and ".join(labels)
                + "."
            )
        else:
            parts.append("That falls outside what I can help with.")
        parts.append(
            "I can't provide that assistance, but I'd be glad to help with a "
            "lawful or help-oriented alternative — for example exploring the "
            "underlying need or connecting with appropriate human support."
        )
    elif disposition == "guide":
        if urgent:
            parts.append(
                "I'm sorry you're going through this — thank you for telling "
                "me; your safety matters."
            )
        if labels:
            parts.append(
                "May I encourage you toward "
                + " And ".join(descriptions.get(p, p) for p in labels)
                + "."
            )
        else:
            parts.append("May I encourage you toward patience and care for those affected.")
        if urgent:
            parts.append(
                "Please also reach out to local emergency or crisis services "
                "or someone you trust — you don't have to face this alone."
            )
    elif disposition == "clarify":
        parts.append(
            "One question so I don't misjudge this: could you tell me more "
            "about what you're trying to do?"
        )
        parts.append("Until then, I'll hold off on that action.")
    elif disposition == "review":
        parts.append(
            "This looks like something a qualified human should assess "
            "before anything proceeds, so I'm pausing the action."
        )
        parts.append("I'm still here and glad to keep talking it through with you.")
    elif disposition == "allow":
        parts.append("That's ordinary work; feel free to proceed.")

    if limited and disposition != "allow":
        parts.append(
            "A note on sources: I have insufficient evidence in this "
            "collection to cite the Fathers here."
        )

    if any(c.review_status == "draft-unreviewed" for c in citations):
        parts.append(
            "A note on interpretation: these source excerpts are draft material "
            "and have not been editorially reviewed."
        )

    text = "\n".join(parts)
    return GuidanceResult(
        text=text,
        citations=citations,
        source_status="verified" if verified else "missing",
        limited=limited,
    )


def _quoted_spans(text: str) -> list[str]:
    """Extract spans between double quotation marks, pairwise (open, close)."""
    idxs = [i for i, ch in enumerate(text) if ch == '"']
    return [text[idxs[i] + 1 : idxs[i + 1]] for i in range(0, len(idxs) - 1, 2)]


def _attributed_quotes(text: str) -> list[str]:
    """Quoted spans presented as a named biblical or patristic source claim."""
    idxs = [i for i, ch in enumerate(text) if ch == '"']
    out = []
    for i in range(0, len(idxs) - 1, 2):
        start, end = idxs[i], idxs[i + 1]
        context = text[max(0, start - 180) : min(len(text), end + 80)]
        if _KNOWN_SOURCE.search(context) or re.search(
            r"\b(?:as taught|as written|according to|quoted from|cited in)\b",
            context,
            re.IGNORECASE,
        ):
            out.append(text[start + 1 : end])
    return out


def assess_output(
    candidate_text: str,
    decision: Any,
    passages: list[Any],
    *,
    prohibited_markers: list[str] | None = None,
) -> OutputCheck:
    """Structural gate on a candidate output before release."""
    problems: list[str] = []
    disposition = _attr(decision, "disposition", "")
    markers = (
        DEFAULT_PROHIBITED_MARKERS
        if prohibited_markers is None
        else tuple(prohibited_markers)
    )
    low = candidate_text.lower()
    if disposition == "refuse":
        for m in markers:
            if m.lower() in low:
                problems.append("prohibited_assistance")
                break

    texts = [
        getattr(p, "text", None) or getattr(p, "quote", None)
        for p in passages or []
        if getattr(p, "text", None) or getattr(p, "quote", None)
    ]
    collapsed = [_collapse_ws(t) for t in texts]

    def supported(span: str) -> bool:
        c = _collapse_ws(span)
        return c != "" and any(c in ct for ct in collapsed)

    # quoted spans not backed by any passage text
    for span in _attributed_quotes(candidate_text):
        if span.strip() and not supported(span):
            problems.append("unsupported_quote")

    # asserted quotation with no passages at all
    if _attributed_quotes(candidate_text) and not texts:
        problems.append("missing_citation")

    return OutputCheck(ok=not problems, problems=problems)


def revise_once(
    candidate_text: str,
    check: OutputCheck,
    revise_fn: Callable[[str, list[str]], str | None],
) -> tuple[str, bool]:
    """One revision attempt, max. No retry loops (plan: no self-rewrites)."""
    if check.ok:
        return candidate_text, False
    try:
        revised = revise_fn(candidate_text, check.problems)
    except Exception:
        return candidate_text, False
    if not isinstance(revised, str) or not revised.strip():
        return candidate_text, False
    return revised, True
