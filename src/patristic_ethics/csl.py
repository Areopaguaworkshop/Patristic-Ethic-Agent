"""CSL-JSON citation lanes for modern and scripture sources.

The patristic seed uses ``corpus.CorpusUnit``. Modern government sources and
scripture use CSL-JSON (Citation Style Language) records, with PEA-specific
fields under ``custom``. Each lane builds its own SQLite/FTS5 database so a
modern source can never be mistaken for patristic evidence.
"""

from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from .corpus import sha256_text

CSL_TYPES = {
    "article",
    "article-journal",
    "article-magazine",
    "article-newspaper",
    "book",
    "chapter",
    "thesis",
    "paper-conference",
    "report",
    "manuscript",
    "document",
    "webpage",
    "post-weblog",
    "speech",
    "interview",
    "broadcast",
    "motion_picture",
    "song",
    "dataset",
    "entry-encyclopedia",
}

LANE_SOURCE_CLASS = {
    "modern": "modern_government",
    "scripture": "scripture",
}

REVIEW_STATES = {"draft-unreviewed", "reviewed"}
RIGHTS_STATES = {
    "public-domain",
    "public-domain-unverified",
    "CC-BY-4.0",
    "CC-BY-SA-4.0",
    "permission-cleared",
}

_SCHEMA = """
DROP TABLE IF EXISTS csl_fts;
DROP TABLE IF EXISTS csl_units;

CREATE TABLE csl_units (
    id TEXT PRIMARY KEY,
    lane TEXT NOT NULL,
    source_class TEXT NOT NULL,
    citation_index TEXT NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    issued TEXT,
    publisher TEXT,
    container_title TEXT,
    number TEXT,
    url TEXT NOT NULL,
    accessed TEXT,
    language TEXT NOT NULL,
    locus TEXT NOT NULL,
    text TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,
    principle_ids TEXT NOT NULL,
    rights_status TEXT NOT NULL,
    rights_evidence TEXT NOT NULL,
    review_status TEXT NOT NULL,
    retrieval_verified INTEGER NOT NULL,
    verification_method TEXT NOT NULL,
    note TEXT,
    csl_json TEXT NOT NULL
);

CREATE VIRTUAL TABLE csl_fts USING fts5(text, title, author, content='');

CREATE TRIGGER csl_fts_ai AFTER INSERT ON csl_units BEGIN
    INSERT INTO csl_fts(rowid, text, title, author)
    VALUES (new.rowid, new.text, new.title, new.author);
END;
CREATE TRIGGER csl_fts_ad AFTER DELETE ON csl_units BEGIN
    INSERT INTO csl_fts(csl_fts, rowid, text, title, author)
    VALUES ('delete', old.rowid, old.text, old.title, old.author);
END;
CREATE TRIGGER csl_fts_au AFTER UPDATE ON csl_units BEGIN
    INSERT INTO csl_fts(csl_fts, rowid, text, title, author)
    VALUES ('delete', old.rowid, old.text, old.title, old.author);
    INSERT INTO csl_fts(rowid, text, title, author)
    VALUES (new.rowid, new.text, new.title, new.author);
END;
"""


def _normalize_ws(value: str) -> str:
    return " ".join(value.split())


def _valid_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _date_string(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    parts = value.get("date-parts")
    if not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], list):
        return None
    nums = parts[0]
    if not 1 <= len(nums) <= 3 or any(type(n) is not int for n in nums):
        return None
    try:
        date(*(nums + [1] * (3 - len(nums))))
    except ValueError:
        return None
    return "-".join(f"{n:02d}" if i else f"{n:04d}" for i, n in enumerate(nums))


def _author_string(value: object) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    names: list[str] = []
    for person in value:
        if not isinstance(person, dict):
            return None
        literal = person.get("literal")
        family = person.get("family")
        if isinstance(literal, str) and literal.strip():
            names.append(literal.strip())
        elif isinstance(family, str) and family.strip():
            given = person.get("given")
            names.append(f"{family.strip()}, {given.strip()}" if isinstance(given, str) and given.strip() else family.strip())
        else:
            return None
    return "; ".join(names)


@dataclass
class CslUnit:
    """One CSL-JSON citation plus the exact stored passage text."""

    id: str
    lane: str
    source_class: str
    citation_index: str
    type: str
    title: str
    author: str
    issued: str | None
    publisher: str | None
    container_title: str | None
    number: str | None
    url: str
    accessed: str | None
    language: str
    locus: str
    text: str
    text_sha256: str
    principle_ids: list[str]
    rights_status: str
    rights_evidence: str
    review_status: str
    retrieval_verified: bool
    verification_method: str
    note: str | None
    csl_json: dict

    @property
    def work(self) -> str:
        return self.title

    @property
    def source_url(self) -> str:
        return self.url

    @classmethod
    def from_record(cls, record: dict, lane: str) -> "CslUnit":
        custom = record.get("custom") or {}
        return cls(
            id=str(record.get("id") or ""),
            lane=lane,
            source_class=str(custom.get("source_class") or ""),
            citation_index=str(custom.get("citation_index") or ""),
            type=str(record.get("type") or ""),
            title=str(record.get("title") or ""),
            author=_author_string(record.get("author")) or "",
            issued=_date_string(record.get("issued")),
            publisher=record.get("publisher"),
            container_title=record.get("container-title"),
            number=record.get("number"),
            url=str(record.get("URL") or ""),
            accessed=_date_string(record.get("accessed")),
            language=str(record.get("language") or ""),
            locus=str(custom.get("locus") or ""),
            text=str(custom.get("text") or ""),
            text_sha256=str(custom.get("text_sha256") or ""),
            principle_ids=list(custom.get("principle_ids") or []),
            rights_status=str(custom.get("rights_status") or ""),
            rights_evidence=str(custom.get("rights_evidence") or ""),
            review_status=str(custom.get("review_status") or ""),
            retrieval_verified=bool(custom.get("retrieval_verified")),
            verification_method=str(custom.get("verification_method") or ""),
            note=custom.get("note"),
            csl_json=record,
        )


def load_csl(path: str | Path) -> list[dict]:
    """Load one CSL-JSON object per line. Raises ValueError with line numbers."""
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
        raise ValueError(f"{path}: no CSL records found")
    return records


def validate_csl(records: list[dict], lane: str) -> list[str]:
    """Return provenance/shape problems; empty means the lane is clean."""
    if lane not in LANE_SOURCE_CLASS:
        return [f"unknown lane {lane!r}"]
    problems: list[str] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        unit = CslUnit.from_record(record, lane)
        label = unit.id or f"#{index}"
        add = lambda msg: problems.append(f"{label}: {msg}")  # noqa: E731

        if not unit.id.strip():
            add("missing id")
        elif unit.id in seen:
            add("duplicate id")
        else:
            seen.add(unit.id)
        if unit.type not in CSL_TYPES:
            add(f"unsupported CSL type {unit.type!r}")
        if not unit.title.strip():
            add("missing title")
        if not unit.author:
            add("missing or invalid author")
        if not unit.issued:
            add("missing or invalid issued date-parts")
        if not _valid_url(unit.url):
            add("missing or invalid URL")
        if not unit.language.strip():
            add("missing language")
        if unit.source_class != LANE_SOURCE_CLASS[lane]:
            add(f"source_class {unit.source_class!r} does not match lane {lane!r}")
        if not unit.citation_index.strip():
            add("missing citation_index")
        if not unit.principle_ids:
            add("missing principle_ids")
        elif any(
            not isinstance(pid, str) or not re.fullmatch(r"PEA-P(?:0[1-9]|10)", pid)
            for pid in unit.principle_ids
        ):
            add("principle_ids must contain PEA principle IDs")
        elif len(set(unit.principle_ids)) != len(unit.principle_ids):
            add("duplicate principle_ids")
        if not unit.locus.strip():
            add("missing locus")
        if not unit.text.strip():
            add("missing text")
        elif unit.text_sha256 != sha256_text(unit.text):
            add("text_sha256 does not match stored text")
        if not unit.retrieval_verified:
            add("retrieval_verified must be true")
        if not unit.verification_method.strip():
            add("missing verification_method")
        if unit.rights_status not in RIGHTS_STATES:
            add(f"invalid rights_status {unit.rights_status!r}")
        if not _valid_url(unit.rights_evidence):
            add("missing or invalid rights_evidence URL")
        if unit.review_status not in REVIEW_STATES:
            add(f"invalid review_status {unit.review_status!r}")
    return problems


def build_csl_db(records: list[dict], db_path: str | Path, lane: str) -> Path:
    """Build a lane-specific SQLite/FTS5 database atomically."""
    problems = validate_csl(records, lane)
    if problems:
        raise ValueError("; ".join(problems))
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".csl-", suffix=".db", dir=db_path.parent)
    import os

    os.close(fd)
    try:
        conn = sqlite3.connect(temporary)
        try:
            conn.executescript(_SCHEMA)
            for record in records:
                unit = CslUnit.from_record(record, lane)
                conn.execute(
                    "INSERT INTO csl_units VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        unit.id,
                        unit.lane,
                        unit.source_class,
                        unit.citation_index,
                        unit.type,
                        unit.title,
                        unit.author,
                        unit.issued,
                        unit.publisher,
                        unit.container_title,
                        unit.number,
                        unit.url,
                        unit.accessed,
                        unit.language,
                        unit.locus,
                        unit.text,
                        unit.text_sha256,
                        json.dumps(unit.principle_ids),
                        unit.rights_status,
                        unit.rights_evidence,
                        unit.review_status,
                        int(unit.retrieval_verified),
                        unit.verification_method,
                        unit.note,
                        json.dumps(record, ensure_ascii=False, sort_keys=True),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        os.replace(temporary, db_path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return db_path


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_unit(row: sqlite3.Row) -> CslUnit:
    return CslUnit(
        id=row["id"],
        lane=row["lane"],
        source_class=row["source_class"],
        citation_index=row["citation_index"],
        type=row["type"],
        title=row["title"],
        author=row["author"],
        issued=row["issued"],
        publisher=row["publisher"],
        container_title=row["container_title"],
        number=row["number"],
        url=row["url"],
        accessed=row["accessed"],
        language=row["language"],
        locus=row["locus"],
        text=row["text"],
        text_sha256=row["text_sha256"],
        principle_ids=json.loads(row["principle_ids"]),
        rights_status=row["rights_status"],
        rights_evidence=row["rights_evidence"],
        review_status=row["review_status"],
        retrieval_verified=bool(row["retrieval_verified"]),
        verification_method=row["verification_method"],
        note=row["note"],
        csl_json=json.loads(row["csl_json"]),
    )


def search_csl(db_path: str | Path, query: str, limit: int = 5) -> list[CslUnit]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT u.* FROM csl_fts f JOIN csl_units u ON u.rowid = f.rowid "
            "WHERE csl_fts MATCH ? ORDER BY bm25(csl_fts) LIMIT ?",
            (query, limit),
        ).fetchall()
        return [_row_to_unit(row) for row in rows]
    finally:
        conn.close()


def get_csl_unit(db_path: str | Path, unit_id: str) -> CslUnit | None:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM csl_units WHERE id = ?", (unit_id,)).fetchone()
        return _row_to_unit(row) if row else None
    finally:
        conn.close()


def verify_csl_quote(db_path: str | Path, unit_id: str, quote: str) -> bool:
    unit = get_csl_unit(db_path, unit_id)
    if unit is None:
        return False
    return _normalize_ws(quote) in _normalize_ws(unit.text)
