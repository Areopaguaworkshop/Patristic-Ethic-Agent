"""Abrupt process exits and competing claims; effects are local test journals."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from patristic_ethics.runtime_store import RuntimeStore

ROOT = Path(__file__).resolve().parents[2]
ACTION = {"tool": "send_email", "arguments": {"body": "test"}}
CONTEXT = {"session_id": "recovery-session", "context_limited": True}
POLICY = "test-policy"

WORKER = '''
import json, os, sys
from patristic_ethics.runtime_store import RuntimeStore
store = RuntimeStore(sys.argv[1])
action, context = json.loads(sys.argv[2]), json.loads(sys.argv[3])
rid = store.claim_matching_approval("recovery-session", action, context, "test-policy")
if rid is None:
    print("blocked", flush=True)
    sys.exit(0)
if sys.argv[4] == "before-effect":
    os._exit(17)
with open(sys.argv[5], "ab") as effects:
    effects.write(b"effect\\n")
    effects.flush()
    os.fsync(effects.fileno())
if sys.argv[4] == "after-effect":
    os._exit(17)
assert store.mark_dispatched(rid)
if sys.argv[4] == "after-record":
    os._exit(17)
print("dispatched", flush=True)
'''


def approved_store(tmp_path, monkeypatch):
    db = tmp_path / "runtime.db"
    store = RuntimeStore(db)
    rid = store.open_review("recovery-session", ACTION, CONTEXT, POLICY)
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "test-only-token")
    store.resolve_review(rid, "approved", "test-only-token", note="test fixture")
    return db, store, rid


def worker_args(db, phase, effects):
    return [sys.executable, "-c", WORKER, str(db), json.dumps(ACTION),
            json.dumps(CONTEXT), phase, str(effects)]


@pytest.mark.parametrize("phase, expected_effects, state", [
    ("before-effect", 0, "attempted"),
    ("after-effect", 1, "attempted"),
    ("after-record", 1, "dispatched"),
])
def test_crash_does_not_replay_approval_and_operator_can_inspect(tmp_path, monkeypatch, phase, expected_effects, state):
    db, store, rid = approved_store(tmp_path, monkeypatch)
    effects = tmp_path / "effects"
    crashed = subprocess.run(worker_args(db, phase, effects), cwd=ROOT, capture_output=True, timeout=10)
    assert crashed.returncode == 17, crashed.stderr
    # A fresh process opens the committed database after os._exit (no cleanup handlers).
    retried = subprocess.run(worker_args(db, "normal", effects), cwd=ROOT, capture_output=True, timeout=10)
    assert retried.returncode == 0, retried.stderr
    assert retried.stdout == b"blocked\n"
    assert (len(effects.read_text().splitlines()) if effects.exists() else 0) == expected_effects
    assert store.get_review(rid)["dispatch_state"] == state
    inspected = subprocess.run([sys.executable, "-m", "patristic_ethics.operator", "--db", str(db), "attempts"],
                               cwd=ROOT, capture_output=True, timeout=10)
    assert inspected.returncode == 0, inspected.stderr
    rows = json.loads(inspected.stdout)
    assert [row["review_id"] for row in rows] == ([] if state == "dispatched" else [rid])
    assert store.get_review(rid)["dispatch_state"] == state
    store.conn.close()


def test_competing_processes_claim_one_approval_once(tmp_path, monkeypatch):
    db, store, rid = approved_store(tmp_path, monkeypatch)
    effects = tmp_path / "effects"
    processes = []
    try:
        for _ in range(4):
            processes.append(subprocess.Popen(worker_args(db, "normal", effects), cwd=ROOT,
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 0, stderr
            outputs.append(stdout)
        assert outputs.count(b"dispatched\n") == 1
        assert outputs.count(b"blocked\n") == 3
        assert effects.read_text() == "effect\n"
        assert store.get_review(rid)["dispatch_state"] == "dispatched"
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()
        store.conn.close()


@pytest.mark.parametrize("failure", ["downstream", "completion-record"])
def test_proxy_failure_after_effect_leaves_attempt_unreplayed(tmp_path, monkeypatch, failure):
    import anyio
    from mcp import Client
    import mcp.types as types
    from mcp.shared.exceptions import MCPError
    from patristic_ethics.assess import AssessResult
    from patristic_ethics.proxy import assess_tool_call, create_proxy_server

    db, store, rid = approved_store(tmp_path, monkeypatch)
    effects = []

    class Downstream:
        async def list_tools(self, cursor=None):
            return types.ListToolsResult(tools=[])

        async def call_tool(self, name, arguments):
            effects.append((name, arguments))
            if failure == "downstream":
                raise RuntimeError("effect completed but reply lost")
            return types.CallToolResult(content=[], isError=False)

    def gate(name, arguments):
        return assess_tool_call(
            name, arguments, session_id="recovery-session",
            assess_fn=lambda envelope: AssessResult(action="review", audit={"policy_version": POLICY}),
            open_review_fn=store.open_review, claim_approval_fn=store.claim_matching_approval,
            runtime_store=store,
        )

    def record(review_id):
        if failure == "completion-record":
            raise OSError("completion record unavailable")
        return store.mark_dispatched(review_id)

    async def probe():
        proxy = create_proxy_server(Downstream(), gate, record)
        async with Client(proxy, raise_exceptions=False, read_timeout_seconds=2) as host:
            with pytest.raises(MCPError, match="Internal server error"):
                await host.call_tool(ACTION["tool"], ACTION["arguments"])
            assert store.get_review(rid)["dispatch_state"] == "attempted"
            repeated = await host.call_tool(ACTION["tool"], ACTION["arguments"])
            assert repeated.is_error
            assert len(effects) == 1
            assert [row["review_id"] for row in store.stuck_attempts(older_than_s=0)] == [rid]

    try:
        anyio.run(probe)
    finally:
        store.conn.close()
