"""Further-reading bibliography for ethical principles.

Secondary sources are listed for further study. They are not interpreted,
quoted, or used as runtime guidance. The canonical file is JSONL with CSL
fields plus PEA fields under ``custom``.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .csl import CSL_TYPES

PRINCIPLE_IDS = {f"PEA-P{i:02d}" for i in range(1, 11)}
REVIEW_STATES = {"draft-unreviewed", "reviewed"}
RIGHTS_STATES = {
    "public-domain",
    "public-domain-unverified",
    "open-access",
    "library",
    "purchase",
    "unknown",
}


def load_further_reading(path: str | Path) -> list[dict]:
    """Load one CSL/PEA record per line."""
    records: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: malformed JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_no}: expected a JSON object")
            records.append(record)
    return records


def _valid_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _valid_names(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for person in value:
        if not isinstance(person, dict):
            return False
        if not (person.get("literal") or person.get("family")):
            return False
    return True


def validate_further_reading(records: list[dict], known_unit_ids: set[str]) -> list[str]:
    """Return bibliographic problems; empty means the list is clean."""
    problems: list[str] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        label = str(record.get("id") or f"#{index}")
        add = lambda msg: problems.append(f"{label}: {msg}")  # noqa: E731
        custom = record.get("custom") or {}
        if not label.strip():
            add("missing id")
        elif label in seen:
            add("duplicate id")
        else:
            seen.add(label)
        if record.get("type") not in CSL_TYPES:
            add("unsupported CSL type")
        if not isinstance(record.get("title"), str) or not record["title"].strip():
            add("missing title")
        if not (_valid_names(record.get("author")) or _valid_names(record.get("editor"))):
            add("missing author or editor")
        if not isinstance(record.get("issued"), dict):
            add("missing issued date-parts")
        if not any(record.get(key) for key in ("URL", "DOI", "ISBN")):
            add("missing URL, DOI, or ISBN")
        if record.get("URL") and not _valid_url(record["URL"]):
            add("invalid URL")
        if not isinstance(record.get("language"), str) or not record["language"].strip():
            add("missing language")
        if custom.get("source_class") != "further_reading":
            add("source_class must be further_reading")
        principles = custom.get("principle_ids")
        if not isinstance(principles, list) or not principles:
            add("missing principle_ids")
        elif any(not isinstance(pid, str) or pid not in PRINCIPLE_IDS for pid in principles):
            add("principle_ids contains an unknown principle")
        elif len(set(principles)) != len(principles):
            add("duplicate principle_ids")
        linked = custom.get("linked_unit_ids")
        if linked is not None:
            if not isinstance(linked, list) or any(
                not isinstance(uid, str) or uid not in known_unit_ids for uid in linked
            ):
                add("linked_unit_ids contains an unknown unit")
        if custom.get("review_status") not in REVIEW_STATES:
            add(f"invalid review_status {custom.get('review_status')!r}")
        if custom.get("rights_status") not in RIGHTS_STATES:
            add(f"invalid rights_status {custom.get('rights_status')!r}")
        if not isinstance(custom.get("rights_evidence"), str) or not custom["rights_evidence"].strip():
            add("missing rights_evidence")
        if not isinstance(custom.get("verification_method"), str) or not custom["verification_method"].strip():
            add("missing verification_method")
        if custom.get("quote"):
            add("further reading must not contain a quotation")
    return problems


def group_by_principle(records: list[dict]) -> dict[str, list[dict]]:
    """Group records by PEA principle ID. A record may appear under several."""
    grouped: dict[str, list[dict]] = {pid: [] for pid in sorted(PRINCIPLE_IDS)}
    for record in records:
        for pid in (record.get("custom") or {}).get("principle_ids") or []:
            if pid in grouped:
                grouped[pid].append(record)
    return {pid: items for pid, items in grouped.items() if items}


VERIFICATION_LABELS = {
    "crossref-match": "verified: Crossref",
    "url-match": "verified: URL title",
    "lead-only": "LEAD ONLY",
    "url-blocked": "blocked",
    "url-pdf-unchecked": "PDF unchecked",
    "crossref-partial": "NEEDS REVIEW: partial Crossref",
    "crossref-mismatch": "MISMATCH",
    "crossref-not-found": "DOI NOT FOUND",
    "url-mismatch": "NEEDS REVIEW: URL title mismatch",
    "url-no-metadata": "NEEDS REVIEW: no metadata",
}


def verification_label(status: str | None) -> str | None:
    return VERIFICATION_LABELS.get(status, status) if status else None


def _year(record: dict) -> str:
    parts = (record.get("issued") or {}).get("date-parts") or []
    if parts and parts[0]:
        return str(parts[0][0])
    return "n.d."


def _author(record: dict) -> str:
    names = record.get("author") or record.get("editor") or []
    labels = []
    for person in names:
        labels.append(person.get("literal") or ", ".join(
            part for part in (person.get("family"), person.get("given")) if part
        ))
    return "; ".join(labels) or "Unknown"


def render_markdown(records: list[dict]) -> str:
    """Render a grouped bibliography without quotations or interpretation."""
    grouped = group_by_principle(records)
    lines = ["# Further reading by principle", ""]
    if not grouped:
        lines.append("No further-reading records have been imported.")
    for pid, items in grouped.items():
        lines.append(f"## {pid}")
        lines.append("")
        for record in items:
            identifier = record.get("DOI") or record.get("ISBN") or record.get("URL") or ""
            lines.append(
                f"- {_author(record)}. *{record.get('title', '')}*. "
                f"{record.get('publisher', '')} {_year(record)}. {identifier}".rstrip()
            )
            note = (record.get("custom") or {}).get("note")
            if note:
                lines.append(f"  {note}")
            status = (record.get("custom") or {}).get("verification_status")
            label = verification_label(status)
            if label:
                lines.append(f"  Verification: **{label}**")
                if status in {
                    "crossref-partial", "crossref-mismatch", "crossref-not-found",
                    "url-mismatch", "url-no-metadata",
                }:
                    flag = (record.get("custom") or {}).get("verification_notes")
                    if flag:
                        lines.append(f"  Flag: {flag}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_text(record: dict) -> str:
    """One-line text form for CLI output."""
    identifier = record.get("DOI") or record.get("ISBN") or record.get("URL") or ""
    status = (record.get("custom") or {}).get("verification_status")
    label = verification_label(status)
    suffix = f" | {label}" if label else ""
    return (
        f"{record.get('id', '')} | {_author(record)} | {record.get('title', '')} "
        f"| {_year(record)} | {identifier}{suffix}"
    )
