"""Offline in-process MCP round trips for the PEA server (plan M4).

No subprocess, no network: the server runs in-process via the installed
mcp v2 Client/MCPServer pair (pattern proven by tests/test_sdk_pin.py),
against corpus/units.db when present, else a tiny tmp db built from an
inline JSONL. FakeInterpreter scripts the observations.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import anyio
from mcp import Client

from patristic_ethics.context import build_envelope
from patristic_ethics.corpus import build_db, sha256_text
from patristic_ethics.interpreter import FakeInterpreter, Observation
from patristic_ethics.mcp_server import create_server

ROOT = Path(__file__).resolve().parents[2]
REPO_DB = ROOT / "corpus" / "units.db"
FIXTURES = ROOT / "tests" / "fixtures" / "assess"

BENIGN_OBS = Observation(
    requested_assistance="how to terminate a Linux process",
    affected_parties=[],
    topics=["linux", "processes"],
    expressed_intent="technical task on my own machine",
    evidence=[],
    benign_explanations=["kill a process is a standard technical phrase"],
    unresolved_ambiguity=[],
    confidence=0.9,
)

HARM_OBS = Observation(
    requested_assistance="tell me the method to poison the dog without getting caught",
    affected_parties=["neighbor", "animal"],
    topics=["assault", "animal harm"],
    expressed_intent="harm the neighbor's dog",
    evidence=[],
    benign_explanations=[],
    unresolved_ambiguity=[],
    confidence=0.95,
)

REVIEW_OBS = Observation(
    requested_assistance="something about assault, details unclear",
    affected_parties=[],
    topics=["assault"],
    expressed_intent="unclear",
    evidence=[],
    benign_explanations=[],
    unresolved_ambiguity=["the target of the action is unknown"],
    confidence=None,
)

PEACE_TEXT = "Blessed are the peacemakers, for they shall be called sons of God."

_TOOL_NAMES = {"check_action", "search_corpus", "get_passage", "cite_father"}
_FORBIDDEN_PARAM_SUBSTRINGS = ("approve", "override", "release")


def _seed_jsonl(tmp_path: Path) -> Path:
    units = [
        {
            "id": "u-peace",
            "principle_ids": ["PEA-P01"],
            "author": "Augustine",
            "work": "Sermon on the Mount",
            "locus": "Mt 5:9",
            "language": "en",
            "edition": "test",
            "translator": None,
            "source_id": "s1",
            "source_url": "https://example.com/u-peace",
            "rights_status": "public-domain",
            "rights_evidence": "https://example.com/license",
            "retrieved": "2026-10-01",
            "text": PEACE_TEXT,
            "text_sha256": sha256_text(PEACE_TEXT),
            "offset_start": None,
            "offset_end": None,
            "cts_urn": None,
            "review_status": "draft-unreviewed",
            "retrieval_verified": False,
            "note": None,
        },
    ]
    path = tmp_path / "seed.jsonl"
    path.write_text("\n".join(json.dumps(u) for u in units), encoding="utf-8")
    return path


def _db_path(tmp_path: Path) -> Path:
    """corpus/units.db when present; else a tmp db from the inline JSONL."""
    if REPO_DB.is_file():
        return REPO_DB
    return build_db(_seed_jsonl(tmp_path), tmp_path / "units.db")


def _known_unit(db_path: Path) -> tuple[str, str]:
    """First English unit's id and a searchable ASCII word from its text."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT id, text FROM units WHERE text IS NOT NULL AND language='en' LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "no English unit with text in the corpus db"
    words = [w for w in row["text"].split() if w.isascii() and w.isalpha() and len(w) >= 5]
    assert words, "no searchable ASCII word in the unit text"
    return row["id"], words[0]


def _server(tmp_path: Path, db_path: Path):
    interp = FakeInterpreter(
        {
            "kill a process": BENIGN_OBS,
            "poison it": HARM_OBS,
            "assault": REVIEW_OBS,
        }
    )
    return create_server(
        db_path=db_path,
        policy_path=ROOT / "policy" / "rules.json",
        interpreter_factory=lambda: interp,
        runtime_db_path=tmp_path / "runtime.db",
    )


def test_tools_listed_and_no_approval_params(tmp_path):
    db = _db_path(tmp_path)
    server = _server(tmp_path, db)

    async def probe():
        async with Client(server, raise_exceptions=True, read_timeout_seconds=2.0) as c:
            listed = (await c.list_tools()).tools
            names = {t.name for t in listed}
            assert names == _TOOL_NAMES, f"tool names: {names}"
            for t in listed:
                props = t.input_schema.get("properties", {})
                for pname in props:
                    low = pname.lower()
                    for bad in _FORBIDDEN_PARAM_SUBSTRINGS:
                        assert bad not in low, f"{t.name} accepts {pname!r}"

    anyio.run(probe)


def test_check_action_benign_and_refuse(tmp_path):
    db = _db_path(tmp_path)
    server = _server(tmp_path, db)
    benign = (FIXTURES / "benign.json").read_text()
    refuse = (FIXTURES / "refuse.json").read_text()

    async def probe():
        async with Client(server, raise_exceptions=True, read_timeout_seconds=2.0) as c:
            ok = await c.call_tool("check_action", {"envelope_json": benign})
            assert not ok.is_error
            sc = ok.structured_content
            assert sc["action"] == "proceed", sc
            assert sc["disposition"] == "allow", sc
            assert sc["error"] is None
            assert sc["policy_review_status"] == "reviewed", sc

            bad = await c.call_tool("check_action", {"envelope_json": refuse})
            assert not bad.is_error
            sc2 = bad.structured_content
            assert sc2["action"] == "refuse", sc2
            assert sc2["non_overridable"] is True, sc2
            assert sc2["review_id"] is None, "refuse must never open a review"

    anyio.run(probe)


def test_check_action_review_opens_pending_review(tmp_path):
    db = _db_path(tmp_path)
    server = _server(tmp_path, db)
    runtime_db = tmp_path / "runtime.db"
    envelope_json = build_envelope(
        request="help me with something about assault, details unclear"
    ).model_dump_json()

    async def probe():
        async with Client(server, raise_exceptions=True, read_timeout_seconds=2.0) as c:
            r = await c.call_tool("check_action", {"envelope_json": envelope_json})
            sc = r.structured_content
            assert sc["action"] == "review", sc
            assert sc["review_id"], "review disposition must open a review"

            from patristic_ethics import runtime_store

            store = runtime_store.RuntimeStore(runtime_db)
            try:
                row = store.get_review(sc["review_id"])
                assert row is not None and row["status"] == "pending", row
            finally:
                store.conn.close()

    anyio.run(probe)


def test_search_corpus_get_passage_cite_father(tmp_path):
    db = _db_path(tmp_path)
    server = _server(tmp_path, db)
    unit_id, token = _known_unit(db)

    async def probe():
        async with Client(server, raise_exceptions=True, read_timeout_seconds=2.0) as c:
            s = await c.call_tool("search_corpus", {"query": token, "limit": 5})
            assert not s.is_error
            units = s.structured_content["units"]
            assert units, f"known token {token!r} must hit"
            assert any(u["id"] == unit_id for u in units), [u["id"] for u in units]
            assert all(
                u["review_status"] in {"draft-unreviewed", "reviewed"} for u in units
            )

            p = await c.call_tool("get_passage", {"unit_id": unit_id})
            assert not p.is_error
            pu = p.structured_content
            assert pu["found"] is True and pu["unit"]["id"] == unit_id, pu
            assert pu["unit"]["review_status"] in {"draft-unreviewed", "reviewed"}, pu

            miss = await c.call_tool("get_passage", {"unit_id": "u-no-such-unit"})
            mu = miss.structured_content
            assert mu["found"] is False and mu["unit"] is None, mu
            assert mu["error"] and "PEA_UNKNOWN_UNIT" in mu["error"], mu

            nonsense = await c.call_tool("cite_father", {"topic": "zzqxjwv", "limit": 3})
            assert not nonsense.is_error
            nc = nonsense.structured_content
            assert nc["citations"] == [], nc
            assert nc["source_status"] == "missing", nc
            assert nc["text"] == "insufficient evidence in this collection", nc

    anyio.run(probe)
