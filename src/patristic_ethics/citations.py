"""CSL-JSON citation records for primary texts and secondary scholarship.

Primary records link a CSL citation to a reviewed seed unit and keep the CTS
URN where the source provides one. Secondary records link modern scholarship to
one or more primary units; they never enter the patristic quotation database.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .csl import CSL_TYPES
from .corpus import sha256_text

REVIEW_STATES = {"draft-unreviewed", "reviewed"}
SECONDARY_ROLES = {"discovery", "interpretation", "reference"}
SECONDARY_RIGHTS = {
    "public-domain",
    "public-domain-unverified",
    "CC-BY-4.0",
    "CC-BY-SA-4.0",
    "permission-cleared",
    "fair-use-quote",
}


def _load(path: str | Path) -> list[dict]:
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
    if not records:
        raise ValueError(f"{path}: no records found")
    return records


def load_primary_citations(path: str | Path) -> list[dict]:
    return _load(path)


def load_secondary(path: str | Path) -> list[dict]:
    return _load(path)


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


def validate_primary_citations(records: list[dict], seed_units: dict) -> list[str]:
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
        if not _valid_names(record.get("author")):
            add("missing or invalid author")
        if not _valid_url(record.get("URL")):
            add("missing or invalid URL")
        if custom.get("source_class") != "patristic_primary":
            add("source_class must be patristic_primary")
        unit_id = custom.get("unit_id")
        unit = seed_units.get(unit_id) if isinstance(unit_id, str) else None
        if unit is None:
            add("unknown unit_id")
            continue
        if custom.get("unit_text_sha256") != unit.text_sha256:
            add("unit_text_sha256 does not match the seed unit")
        if custom.get("cts_urn") != unit.cts_urn:
            add("cts_urn does not match the seed unit")
        if custom.get("review_status") != unit.review_status:
            add("review_status does not match the seed unit")
        if custom.get("source_url") != unit.source_url:
            add("source_url does not match the seed unit")
    return problems


def validate_secondary(records: list[dict], known_unit_ids: set[str]) -> list[str]:
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
        if not _valid_names(record.get("author")):
            add("missing or invalid author")
        if not isinstance(record.get("issued"), dict):
            add("missing issued date-parts")
        if not _valid_url(record.get("URL")):
            add("missing or invalid URL")
        if custom.get("source_class") != "secondary_scholarship":
            add("source_class must be secondary_scholarship")
        if not isinstance(custom.get("citation_index"), str) or not custom["citation_index"].strip():
            add("missing citation_index")
        linked = custom.get("linked_unit_ids")
        if not isinstance(linked, list) or not linked:
            add("missing linked_unit_ids")
        elif any(not isinstance(uid, str) or uid not in known_unit_ids for uid in linked):
            add("linked_unit_ids contains an unknown unit")
        if custom.get("role") not in SECONDARY_ROLES:
            add(f"invalid role {custom.get('role')!r}")
        quote = custom.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            add("missing quote")
        elif custom.get("quote_sha256") != sha256_text(quote):
            add("quote_sha256 does not match the quote")
        if not isinstance(custom.get("quote_locus"), str) or not custom["quote_locus"].strip():
            add("missing quote_locus")
        if custom.get("rights_status") not in SECONDARY_RIGHTS:
            add(f"invalid rights_status {custom.get('rights_status')!r}")
        if not _valid_url(custom.get("rights_evidence")):
            add("missing or invalid rights_evidence")
        if custom.get("review_status") not in REVIEW_STATES:
            add(f"invalid review_status {custom.get('review_status')!r}")
        if not isinstance(custom.get("verification_method"), str) or not custom["verification_method"].strip():
            add("missing verification_method")
    return problems
