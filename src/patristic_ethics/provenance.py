"""Linked CSL-JSON provenance records for corpus units.

`corpus/provenance.jsonl` records the discovery and editorial chain behind a
primary text: repository catalogues, critical editions, and (later) independent
secondary literature. Records link to seed unit IDs; they do not supply runtime
quotations.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .csl import CSL_TYPES

ROLES = {"catalogue", "edition", "secondary_literature"}
REVIEW_STATES = {"draft-unreviewed", "reviewed"}


def _valid_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _has_name(value: object, field: str) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for person in value:
        if not isinstance(person, dict):
            return False
        if not (person.get("literal") or person.get("family")):
            return False
    return True


def load_provenance(path: str | Path) -> list[dict]:
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
        raise ValueError(f"{path}: no provenance records found")
    return records


def validate_provenance(records: list[dict], known_unit_ids: set[str]) -> list[str]:
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
        if not (_has_name(record.get("author"), "author") or _has_name(record.get("editor"), "editor")):
            add("missing author or editor")
        if not isinstance(record.get("issued"), dict):
            add("missing issued date-parts")
        if not _valid_url(record.get("URL")):
            add("missing or invalid URL")
        if custom.get("provenance_role") not in ROLES:
            add(f"invalid provenance_role {custom.get('provenance_role')!r}")
        linked = custom.get("linked_unit_ids")
        if not isinstance(linked, list) or not linked:
            add("missing linked_unit_ids")
        elif any(not isinstance(uid, str) or uid not in known_unit_ids for uid in linked):
            add("linked_unit_ids contains an unknown unit")
        if custom.get("review_status") not in REVIEW_STATES:
            add(f"invalid review_status {custom.get('review_status')!r}")
        if not isinstance(custom.get("note"), str) or not custom["note"].strip():
            add("missing note")
    return problems
