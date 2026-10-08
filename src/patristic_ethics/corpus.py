"""Seed corpus loader, validator, and SQLite FTS5 index (plan M1b).

Every passage in the seed corpus carries verified provenance: an exact raw
source URL, a rights status with evidence URL, a SHA-256 hash of the stored
text, and a review status. The seed JSONL is the canonical data; the SQLite
database is a derived, deterministically rebuildable index.

Fidelity check: `verify_quote` matches a quote against the stored text
with whitespace collapsed; it is deliberately exact — no fuzzy matching.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import tempfile
from datetime import date
from dataclasses import dataclass, field, fields
from pathlib import Path
from urllib.parse import urlparse

UNIT_COLUMNS = (
    "id",
    "principle_ids",
    "author",
    "work",
    "locus",
    "language",
    "edition",
    "translator",
    "source_id",
    "source_url",
    "rights_status",
    "rights_evidence",
    "retrieved",
    "text",
    "text_sha256",
    "offset_start",
    "offset_end",
    "cts_urn",
    "review_status",
    "retrieval_verified",
)

# INSERT statement built once at import time from the fixed column list; all
# values are bound through `?` placeholders (no untrusted input in the SQL).
_INSERT_UNITS_SQL = "".join(
    [
        "INSERT INTO units (",
        ",".join(UNIT_COLUMNS),
        ",note) VALUES (",
        ",".join("?" for _ in UNIT_COLUMNS),
        ",?)",
    ]
)


@dataclass
class CorpusUnit:
    """One verified-provenance passage. Types are lenient: the loader only
    requires the keys to exist; `validate_units` reports the problems."""

    id: str
    principle_ids: list[str]
    author: str
    work: str
    locus: str | None
    language: str
    edition: str
    translator: str | None
    source_id: str
    source_url: str
    rights_status: str
    rights_evidence: str
    retrieved: str
    text: str | None
    text_sha256: str | None
    offset_start: int | None
    offset_end: int | None
    cts_urn: str | None
    review_status: str
    retrieval_verified: bool
    note: str | None = None

    @classmethod
    def from_json(cls, data: dict, line_no: int | None = None) -> "CorpusUnit":
        missing = [c for c in UNIT_COLUMNS if c not in data]
        if missing:
            where = f" (line {line_no})" if line_no is not None else ""
            raise ValueError(f"unit missing fields {missing}{where}")
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def _normalize_ws(s: str) -> str:
    return " ".join(s.split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_seed(path: str | Path) -> list[CorpusUnit]:
    """Load seed JSONL into units. Raises ValueError with line numbers on
    malformed lines or missing fields."""
    path = Path(path)
    units: list[CorpusUnit] = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{i}: malformed JSON: {e}") from e
            if not isinstance(data, dict):
                raise ValueError(f"{path}:{i}: expected a JSON object, got {type(data).__name__}")
            units.append(CorpusUnit.from_json(data, line_no=i))
    if not units:
        raise ValueError(f"{path}: no units found (empty seed file)")
    return units


def validate_units(units: list[CorpusUnit]) -> list[str]:
    """Return a list of provenance problems; empty list means the corpus is clean."""
    problems: list[str] = []
    seen: dict[str, int] = {}
    for i, u in enumerate(units):
        label = u.id if isinstance(u.id, str) and u.id else f"#{i}"
        p = lambda msg: problems.append(f"{label}: {msg}")  # noqa: E731

        if not isinstance(u.id, str):
            p("invalid id")
        elif not u.id.strip():
            p("missing id")
        elif u.id in seen:
            p(f"duplicate id (first at index {seen[u.id]})")
        else:
            seen[u.id] = i

        for name in ("author", "work", "edition", "source_id", "rights_status"):
            value = getattr(u, name)
            if not isinstance(value, str):
                p(f"invalid {name}")
            elif not value.strip():
                p(f"missing {name}")
        if u.locus is not None and not isinstance(u.locus, str):
            p("locus must be a string or null")
        if u.translator is not None and not isinstance(u.translator, str):
            p("translator must be a string or null")

        for name in ("source_url", "rights_evidence"):
            value = getattr(u, name)
            if not isinstance(value, str) or not value.strip():
                p(f"missing {name}")
                continue
            try:
                parsed = urlparse(value)
            except ValueError:
                parsed = None
            if not parsed or parsed.scheme not in {"http", "https"} or not parsed.netloc:
                p(f"missing or invalid {name}")
        if not isinstance(u.language, str) or u.language not in ("grc", "lat", "syr", "en"):
            p(f"unknown language {u.language!r}")
        if not isinstance(u.retrieved, str):
            p("retrieved must be an ISO date")
        else:
            try:
                if date.fromisoformat(u.retrieved).isoformat() != u.retrieved:
                    p("retrieved must be an ISO date")
            except ValueError:
                p("retrieved must be an ISO date")

        if not isinstance(u.principle_ids, list) or not u.principle_ids:
            p("no principle_ids")
        elif any(
            not isinstance(pid, str) or not re.fullmatch(r"PEA-P(?:0[1-9]|10)", pid)
            for pid in u.principle_ids
        ):
            p("principle_ids must contain PEA principle IDs")
        elif len(set(u.principle_ids)) != len(u.principle_ids):
            p("duplicate principle_ids")

        if not isinstance(u.retrieval_verified, bool):
            p("retrieval_verified must be boolean")
        if u.text is not None and not isinstance(u.text, str):
            p("text must be a string or null")
        elif isinstance(u.text, str):
            if not isinstance(u.text_sha256, str) or not u.text_sha256:
                p("text present but text_sha256 missing")
            elif sha256_text(u.text) != u.text_sha256:
                p("text_sha256 does not match stored text")
            if not u.text.strip():
                p("text is empty/whitespace")
        elif u.retrieval_verified:
            p("retrieval_verified true but text is null")
        if u.text is None and u.text_sha256 is not None:
            p("null text must not have text_sha256")

        if not isinstance(u.review_status, str) or u.review_status not in {
            "draft-unreviewed", "reviewed"
        }:
            p(f"invalid review_status {u.review_status!r}")
        elif u.review_status == "reviewed" and (
            not isinstance(u.text, str) or not u.retrieval_verified
        ):
            p("reviewed unit requires verified source text")
    return problems


_SCHEMA = """
DROP TABLE IF EXISTS units_fts;
DROP TABLE IF EXISTS units;

CREATE TABLE units (
    id TEXT PRIMARY KEY,
    principle_ids TEXT NOT NULL,
    author TEXT NOT NULL,
    work TEXT NOT NULL,
    locus TEXT,
    language TEXT NOT NULL,
    edition TEXT NOT NULL,
    translator TEXT,
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    rights_status TEXT NOT NULL,
    rights_evidence TEXT NOT NULL,
    retrieved TEXT NOT NULL,
    text TEXT,
    text_sha256 TEXT,
    offset_start INTEGER,
    offset_end INTEGER,
    cts_urn TEXT,
    review_status TEXT NOT NULL,
    retrieval_verified INTEGER NOT NULL,
    note TEXT
);

CREATE VIRTUAL TABLE units_fts USING fts5(text, author, work, content='');

CREATE TRIGGER units_fts_ai AFTER INSERT ON units BEGIN
    INSERT INTO units_fts(rowid, text, author, work)
    VALUES (new.rowid, new.text, new.author, new.work);
END;
CREATE TRIGGER units_fts_ad AFTER DELETE ON units BEGIN
    INSERT INTO units_fts(units_fts, rowid, text, author, work)
    VALUES ('delete', old.rowid, old.text, old.author, old.work);
END;
CREATE TRIGGER units_fts_au AFTER UPDATE ON units BEGIN
    INSERT INTO units_fts(units_fts, rowid, text, author, work)
    VALUES ('delete', old.rowid, old.text, old.author, old.work);
    INSERT INTO units_fts(rowid, text, author, work)
    VALUES (new.rowid, new.text, new.author, new.work);
END;
"""


def build_db(seed_path: str | Path, db_path: str | Path) -> Path:
    """Build a replacement index, publishing it only after a successful commit."""
    db_path = Path(db_path)
    units = load_seed(seed_path)
    problems = validate_units(units)
    if problems:
        raise ValueError("refusing to index corpus with problems: " + "; ".join(problems))
    # Same directory keeps replacement atomic on the destination filesystem.
    with tempfile.NamedTemporaryFile(dir=db_path.parent, prefix=f".{db_path.name}.",
                                     suffix=".tmp", delete=False) as staged:
        staged_path = Path(staged.name)
    try:
        conn = sqlite3.connect(staged_path)
        try:
            conn.executescript(_SCHEMA)
            for u in units:
                conn.execute(
                    _INSERT_UNITS_SQL,
                    (
                        u.id,
                        json.dumps(u.principle_ids),
                        u.author,
                        u.work,
                        u.locus,
                        u.language,
                        u.edition,
                        u.translator,
                        u.source_id,
                        u.source_url,
                        u.rights_status,
                        u.rights_evidence,
                        u.retrieved,
                        u.text,
                        u.text_sha256,
                        u.offset_start,
                        u.offset_end,
                        u.cts_urn,
                        u.review_status,
                        1 if u.retrieval_verified else 0,
                        u.note,
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        staged_path.replace(db_path)
    finally:
        staged_path.unlink(missing_ok=True)
    return db_path


def _row_to_unit(row: sqlite3.Row) -> CorpusUnit:
    return CorpusUnit(
        id=row["id"],
        principle_ids=json.loads(row["principle_ids"]),
        author=row["author"],
        work=row["work"],
        locus=row["locus"],
        language=row["language"],
        edition=row["edition"],
        translator=row["translator"],
        source_id=row["source_id"],
        source_url=row["source_url"],
        rights_status=row["rights_status"],
        rights_evidence=row["rights_evidence"],
        retrieved=row["retrieved"],
        text=row["text"],
        text_sha256=row["text_sha256"],
        offset_start=row["offset_start"],
        offset_end=row["offset_end"],
        cts_urn=row["cts_urn"],
        review_status=row["review_status"],
        retrieval_verified=bool(row["retrieval_verified"]),
        note=row["note"],
    )


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def search_passages(db_path: str | Path, query: str, limit: int = 5) -> list[CorpusUnit]:
    """FTS5 MATCH over text/author/work, bm25-ordered. Rows without text are
    skipped (nothing to match)."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT u.* FROM units_fts f JOIN units u ON u.rowid = f.rowid "
            "WHERE units_fts MATCH ? AND u.text IS NOT NULL "
            "ORDER BY bm25(units_fts) LIMIT ?",
            (query, limit),
        ).fetchall()
        return [_row_to_unit(r) for r in rows]
    finally:
        conn.close()


def get_passage(db_path: str | Path, unit_id: str) -> CorpusUnit | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM units WHERE id = ?", (unit_id,)).fetchone()
        return _row_to_unit(row) if row else None
    finally:
        conn.close()


def verify_quote(db_path: str | Path, unit_id: str, quote: str) -> bool:
    """Fidelity check: exact substring of the stored text after collapsing
    whitespace. No fuzzy matching, no normalization beyond whitespace."""
    unit = get_passage(db_path, unit_id)
    if unit is None or unit.text is None:
        return False
    return _normalize_ws(quote) in _normalize_ws(unit.text)
