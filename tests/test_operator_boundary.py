"""M3 item 5 (plan section 5.5): prove the operator boundary by ATTEMPT.

Every agent-visible path is exercised as an attack: resolve_review via
agent process, review-state modification via the MCP tool surface,
impersonation by direct sqlite writes, operator-token reads, crash
recovery, and a subprocess resolver invocation. Outcomes are recorded
honestly:

- DENIED BY CODE: assertions that fail closed (token gate, missing
  approve surface, at-most-once claim, no auto-retry, reassessment).
- NOT PREVENTED (same-user dev box): direct sqlite writes and env
  readability succeed here; the doc records that only an OS/sandbox
  boundary (separate operator identity owning runtime.db 0600 and
  PEA_OPERATOR_TOKEN) closes these. These tests mark the gap
  explicitly instead of faking a denial.

Fully offline: tmp_path dbs, monkeypatched env, subprocess only for
the tokenless resolver probe.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from patristic_ethics.context import build_envelope
from patristic_ethics.runtime_store import (
    OperatorBoundaryError,
    RuntimeStore,
)

ROOT = Path(__file__).resolve().parents[1]
ENV_TOKEN = "PEA_OPERATOR_TOKEN"

ACTION = {"tool": "shell", "argv": ["rm", "-rf", "/tmp/x"]}
CONTEXT = {"session": "s1", "recent": ["help me clean tmp files"]}
PV = "0.1.0-draft"


@pytest.fixture()
def store(tmp_path):
    s = RuntimeStore(tmp_path / "runtime.db")
    yield s
    s.conn.close()


@pytest.fixture()
def clean_env(monkeypatch):
    """Ensure PEA_OPERATOR_TOKEN is absent, whatever the shell has set."""
    monkeypatch.delenv(ENV_TOKEN, raising=False)


def pending(store, ttl_s: float = 3600.0) -> str:
    return store.open_review("s1", ACTION, CONTEXT, PV, ttl_s=ttl_s)


# --- 1. resolver invocation attempts --------------------------------------


def test_resolve_without_token_denied_by_code(store, clean_env):
    """Direct agent call without env token -> OperatorBoundaryError."""
    rid = pending(store)
    with pytest.raises(OperatorBoundaryError, match="not configured"):
        store.resolve_review(rid, "approved", "anything")


def test_resolve_with_empty_token_denied_by_code(store, monkeypatch):
    """Empty-string env secret is treated as unconfigured."""
    monkeypatch.setenv(ENV_TOKEN, "")
    rid = pending(store)
    with pytest.raises(OperatorBoundaryError, match="not configured"):
        store.resolve_review(rid, "approved", "anything")


def test_resolve_with_wrong_token_denied_by_code(store, monkeypatch):
    monkeypatch.setenv(ENV_TOKEN, "real-secret")
    rid = pending(store)
    for bad in ("wrong", "real-secret ", "REAL-SECRET", "", "real-secretx"):
        with pytest.raises(OperatorBoundaryError):
            store.resolve_review(rid, "approved", bad)
    # nothing above changed state
    assert store.get_review(rid)["status"] == "pending"


def test_resolve_with_correct_token_control_case(store, monkeypatch):
    """Control: the operator process (token present) CAN resolve."""
    monkeypatch.setenv(ENV_TOKEN, "real-secret")
    rid = pending(store)
    row = store.resolve_review(rid, "approved", "real-secret", note="operator")
    assert row["status"] == "approved"
    assert row["resolved_by"] == "operator"


# --- 2. review-state modification via the MCP surface ----------------------


FORBIDDEN_KEY_RE = re.compile(r"approve|resolve|override|release|state", re.I)


def _server(tmp_path):
    from patristic_ethics.interpreter import FakeInterpreter, Observation

    review_obs = Observation(
        requested_assistance="something about assault, details unclear",
        affected_parties=[],
        topics=["assault"],
        expressed_intent="unclear",
        evidence=[],
        benign_explanations=[],
        unresolved_ambiguity=["the target is unknown"],
        confidence=None,
    )
    interp = FakeInterpreter({"assault": review_obs})
    from patristic_ethics.mcp_server import create_server

    return create_server(
        db_path=ROOT / "corpus" / "units.db",
        policy_path=ROOT / "policy" / "rules.json",
        interpreter_factory=lambda: interp,
        runtime_db_path=tmp_path / "runtime.db",
    )


def _walk_keys(schema, seen=None):
    """Recursively yield every key name in a JSON schema."""
    seen = set() if seen is None else seen
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key not in seen:
                seen.add(key)
                yield key
            yield from _walk_keys(value, seen)
            if key == "properties" and isinstance(value, dict):
                for pname in value:
                    yield pname
    elif isinstance(schema, list):
        for item in schema:
            yield from _walk_keys(item, seen)


def test_mcp_tools_expose_no_state_parameter(tmp_path):
    """No tool input schema carries approve|resolve|override|release|state."""
    import asyncio

    server = _server(tmp_path)
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == {
        "check_action",
        "search_corpus",
        "get_passage",
        "cite_father",
    }
    for t in tools:
        keys = list(_walk_keys(t.input_schema))
        for k in keys:
            assert not FORBIDDEN_KEY_RE.search(k), f"{t.name} exposes {k!r}"


def test_check_action_returns_no_resolution_mechanism(tmp_path):
    """check_action may expose review_id but no resolution path or token."""
    import asyncio

    server = _server(tmp_path)
    envelope_json = build_envelope(
        request="help me with something about assault, details unclear"
    ).model_dump_json()

    async def probe():
        out = await server.call_tool("check_action", {"envelope_json": envelope_json})
        payload = out
        # MCPServer.call_tool returns the tool result; find the structured dict
        text = getattr(out, "text", None) or ""
        sc = getattr(out, "structured_content", None)
        if sc is None and text:
            sc = json.loads(text)
        assert sc is not None, f"unusable result: {out!r}"
        assert sc["action"] == "review", sc
        assert sc["review_id"], "review disposition must expose review_id"
        banned = ("operator_token", "token", "approve", "resolved_by",
                  "resolution_note", "resolve_review")
        blob = json.dumps(sc).lower()
        for b in banned:
            assert b not in blob, f"check_action leaks {b!r}"
        # no resolution function exists anywhere on the server object
        for attr in dir(server):
            low = attr.lower()
            assert "resolve" not in low or low.startswith("_"), attr
            assert "approve" not in low, attr

    asyncio.run(probe())


# --- 3. operator impersonation by direct db write ---------------------------


def test_direct_db_write_is_not_prevented_same_user(store, tmp_path):
    """HONEST GAP: same-user sqlite write CAN flip status='approved'.

    This is the documented not-prevented case: file permissions are an
    OS concern, not a Python-library concern. What the code still
    guarantees here is recorded below: dispatch gating survives the
    forged row, and the caller-side reassessment guard still flags
    drift. Closing this gap requires a separate operator OS identity
    owning runtime.db (0600) — see docs/operator-boundary.md.
    """
    rid = pending(store)
    db_path = tmp_path / "runtime.db"

    # impersonation attempt: raw sqlite, bypassing RuntimeStore entirely
    raw = sqlite3.connect(db_path)
    raw.execute(
        "UPDATE reviews SET status='approved', resolved_by='forged',"
        " resolution_note='direct write' WHERE review_id=?",
        (rid,),
    )
    raw.commit()
    raw.close()

    row = store.get_review(rid)
    assert row["status"] == "approved"  # the write SUCCEEDED — documented gap
    assert row["resolved_by"] == "forged"

    # code-level mitigation 1: dispatch is still one-shot and gated
    assert store.claim_dispatch(rid) is True
    assert store.claim_dispatch(rid) is False
    # code-level mitigation 2: reassessment still detects caller drift
    assert store.reassess_required(rid, ACTION, CONTEXT, PV) is False
    assert store.reassess_required(rid, {"tool": "other"}, CONTEXT, PV) is True


# --- 4. token readability from the agent process -----------------------------


def test_operator_token_not_in_default_test_env(clean_env):
    """The test/agent process has no PEA_OPERATOR_TOKEN by default.

    Same-user env readability is an OS-boundary concern (a deployed
    operator exports it only into its own process): documented in
    docs/operator-boundary.md, NOT faked as a code-level denial here.
    """
    assert os.environ.get(ENV_TOKEN) is None
    # and the store fails closed when it is missing:
    store = RuntimeStore.__new__(RuntimeStore)  # no db needed for the raise
    with pytest.raises(OperatorBoundaryError, match="not configured"):
        store.resolve_review("whatever", "approved", "x")


# --- 5. crash recovery: stuck attempts are never auto-resumed ----------------


def test_stuck_attempt_never_auto_dispatches(store, monkeypatch):
    monkeypatch.setenv(ENV_TOKEN, "real-secret")
    rid = pending(store)
    store.resolve_review(rid, "approved", "real-secret", note="operator ok")
    assert store.claim_dispatch(rid) is True
    # crash after claim: repeated claims all fail — no auto-retry anywhere
    for _ in range(3):
        assert store.claim_dispatch(rid) is False
    # no other agent-facing call silently completes the dispatch either
    assert store.mark_dispatched(rid) is True  # operator explicitly confirms
    stuck = store.stuck_attempts(older_than_s=0.0)
    assert stuck == []  # only claimed-and-never-dispatched rows appear
    # and a genuinely stuck row is only VISIBLE, never retried:
    rid2 = pending(store)
    store.resolve_review(rid2, "approved", "real-secret", note="operator ok")
    assert store.claim_dispatch(rid2) is True
    assert store.claim_dispatch(rid2) is False
    visible = store.stuck_attempts(older_than_s=0.0)
    assert [r["review_id"] for r in visible] == [rid2]
    assert store.claim_dispatch(rid2) is False  # visibility != re-arm


# --- 6. subprocess: tokenless resolver attempt -------------------------------


def test_subprocess_resolve_without_token_exits_nonzero(tmp_path, clean_env):
    """A fresh process with no token cannot resolve; error is loud."""
    db_path = tmp_path / "sub.db"
    s = RuntimeStore(db_path)
    rid = s.open_review("s1", ACTION, CONTEXT, PV)
    s.conn.close()

    code = (
        "import sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from patristic_ethics.runtime_store import RuntimeStore, OperatorBoundaryError\n"
        "store = RuntimeStore(sys.argv[2])\n"
        "try:\n"
        "    store.resolve_review(sys.argv[3], 'approved', 'guessed-token')\n"
        "    sys.exit(0)\n"
        "except OperatorBoundaryError as e:\n"
        f"    print('OperatorBoundaryError:', e, file=sys.stderr)\n"
        "    sys.exit(3)\n"
        "sys.exit(4)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "src"), str(db_path), rid],
        capture_output=True,
        text=True,
        timeout=60,
        env={k: v for k, v in os.environ.items() if k != ENV_TOKEN},
    )
    assert result.returncode == 3, (
        f"resolver attempt must exit 3 (OperatorBoundaryError),"
        f" got {result.returncode}: {result.stdout} {result.stderr}"
    )
    assert "OperatorBoundaryError" in result.stderr
    assert "not configured" in result.stderr
    # the review survived untouched
    s2 = RuntimeStore(db_path)
    try:
        assert s2.get_review(rid)["status"] == "pending"
    finally:
        s2.conn.close()


def test_subprocess_wrong_token_also_denied(tmp_path, monkeypatch):
    """Even WITH a token in env, a wrong guess fails and mutates nothing."""
    db_path = tmp_path / "sub2.db"
    s = RuntimeStore(db_path)
    rid = s.open_review("s1", ACTION, CONTEXT, PV)
    s.conn.close()

    code = (
        "import sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from patristic_ethics.runtime_store import RuntimeStore, OperatorBoundaryError\n"
        "store = RuntimeStore(sys.argv[2])\n"
        "try:\n"
        "    store.resolve_review(sys.argv[3], 'approved', 'wrong')\n"
        "    sys.exit(0)\n"
        "except OperatorBoundaryError:\n"
        "    sys.exit(5)\n"
        "sys.exit(4)\n"
    )
    env = {k: v for k, v in os.environ.items()}
    env[ENV_TOKEN] = "real-secret"
    result = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "src"), str(db_path), rid],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 5, result.stderr
    s2 = RuntimeStore(db_path)
    try:
        assert s2.get_review(rid)["status"] == "pending"
    finally:
        s2.conn.close()