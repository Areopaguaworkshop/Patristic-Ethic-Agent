import json

import pytest

from patristic_ethics.adapters import claude_code, codex
from patristic_ethics.adapters.history import MAX_MESSAGES, collect, remember
from patristic_ethics.context import validate_envelope


@pytest.mark.parametrize("adapter", [codex, claude_code])
def test_observed_dialogue_reaches_next_assessment_without_cross_session_leak(adapter, tmp_path, monkeypatch):
    monkeypatch.setenv("PEA_HISTORY_DB", str(tmp_path / "history.db"))
    captured = []

    def runner(value):
        envelope = json.loads(value) if isinstance(value, str) else value
        validate_envelope(envelope)
        captured.append(envelope)
        result = {"action": "proceed"}
        return json.dumps(result) if adapter is claude_code else result

    def event(name, session="one", **extra):
        return dict(hook_event_name=name, session_id=session, **extra)

    adapter.handle(event("UserPromptSubmit", prompt="Help me plan the project."), runner)
    adapter.handle(event("Stop", last_assistant_message="We can start with the requirements."), runner)
    adapter.handle(event("PreToolUse", tool_name="Read", tool_input={}), runner)
    assert [m["text"] for m in captured[-1]["messages"]] == ["Help me plan the project.", "We can start with the requirements."]
    assert captured[-1]["history"]["complete"] is False
    assert captured[-1]["history"]["collection_errors"]
    adapter.handle(event("UserPromptSubmit", session="two", prompt="Unrelated task"), runner)
    assert captured[-1]["messages"] == []
    other = claude_code if adapter is codex else codex
    assert other.build_envelope(event("UserPromptSubmit", prompt="Different host"))["messages"] == []
    # Rebuilding an adapter envelope reads persisted history across processes/resume.
    assert len(adapter.build_envelope(event("UserPromptSubmit", prompt="Continue"))["messages"]) == 2


def test_blocked_prompt_and_tool_result_are_not_remembered(tmp_path, monkeypatch):
    monkeypatch.setenv("PEA_HISTORY_DB", str(tmp_path / "history.db"))
    payload = dict(hook_event_name="UserPromptSubmit", session_id="s", prompt="Blocked input")
    codex.handle(payload, lambda _: {"action": "refuse"})
    codex.handle(dict(hook_event_name="PostToolUse", session_id="s", tool_response="untrusted result"), lambda _: {"action": "proceed"})
    assert codex.build_envelope(payload)["messages"] == []


def test_history_is_bounded_and_limits_are_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("PEA_HISTORY_DB", str(tmp_path / "history.db"))
    e = codex.build_envelope(dict(hook_event_name="UserPromptSubmit", session_id="s", prompt="x"))
    for i in range(MAX_MESSAGES + 5):
        remember({**e, "request": str(i)}, "proceed")
    collect(e)
    assert len(e["messages"]) == MAX_MESSAGES
    assert e["messages"][0]["text"] == "5"
    assert e["history"]["omitted_ranges"]
    remember({**e, "request": "x" * 20000}, "proceed")
    collect(e)
    assert len(e["messages"]) == 1 and len(e["messages"][0]["text"]) == 16000
    assert e["history"]["omitted_ranges"]


def test_store_failure_and_unknown_session_keep_history_incomplete(tmp_path, monkeypatch):
    path = tmp_path / "broken.db"
    path.write_text("not sqlite")
    monkeypatch.setenv("PEA_HISTORY_DB", str(path))
    e = codex.build_envelope(dict(hook_event_name="UserPromptSubmit", session_id="s", prompt="x"))
    assert "hook history store unavailable" in e["history"]["collection_errors"]
    assert e["history"]["complete"] is False
    e = claude_code.build_envelope(dict(hook_event_name="UserPromptSubmit", prompt="x"))
    assert "history requires a known session id" in e["history"]["collection_errors"]


def test_payload_cannot_choose_history_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PEA_HISTORY_DB", str(tmp_path / "history.db"))
    unrelated = tmp_path / "other-session.jsonl"
    unrelated.write_text("secret from another session")
    e = codex.build_envelope(dict(hook_event_name="UserPromptSubmit", session_id="s", prompt="x", transcript_path=str(unrelated)))
    assert e["messages"] == []
    assert unrelated.read_text() == "secret from another session"


@pytest.mark.parametrize("adapter", [codex, claude_code])
def test_explicit_event_replay_is_deduplicated_but_new_turn_is_preserved(adapter, tmp_path, monkeypatch):
    monkeypatch.setenv("PEA_HISTORY_DB", str(tmp_path / "history.db"))
    payload = dict(hook_event_name="UserPromptSubmit", session_id="s", turn_id="one", prompt="Write a Python function")
    def runner(_):
        result = {"action": "proceed"}
        return json.dumps(result) if adapter is claude_code else result
    adapter.handle(payload, runner)
    adapter.handle(payload, runner)
    assert len(adapter.build_envelope(payload)["messages"]) == 1
    adapter.handle({**payload, "turn_id": "two"}, runner)
    assert len(adapter.build_envelope(payload)["messages"]) == 2


def test_malformed_stored_rows_are_reported_without_adapter_crash(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "history.db"
    monkeypatch.setenv("PEA_HISTORY_DB", str(path))
    payload = dict(hook_event_name="UserPromptSubmit", session_id="s", prompt="x")
    codex.build_envelope(payload)
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO observed(host,session,role,text,truncated) VALUES(?,?,?,?,?)", ("codex", "s", "user", None, 0))
    e = codex.build_envelope(payload)
    assert e["messages"] == []
    assert "hook history store unavailable" in e["history"]["collection_errors"]


@pytest.mark.parametrize("module,adapter", [
    ("patristic_ethics.adapters.codex", codex),
    ("patristic_ethics.adapters.claude_code", claude_code),
])
def test_real_hook_processes_persist_history_and_keep_protocol_clean(module, adapter, tmp_path, monkeypatch):
    import os
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("PEA_HISTORY_DB", str(tmp_path / "history.db"))
    env = {**os.environ, "PEA_BACKEND": "fake", "PEA_DB": str(root / "corpus/units.db"), "PEA_POLICY": str(root / "policy/rules.json")}
    prompt = dict(hook_event_name="UserPromptSubmit", session_id="process-session", turn_id="turn-one", prompt="Write a Python function to add two numbers.")
    stop = dict(hook_event_name="Stop", session_id="process-session", turn_id="turn-one", last_assistant_message="Use addition to sum the two arguments.")
    for payload in (prompt, prompt, stop):
        process = subprocess.run([sys.executable, "-m", module], input=json.dumps(payload), text=True, capture_output=True, timeout=30, cwd=root, env=env)
        assert process.returncode == 0, process.stderr
        assert not process.stderr
        assert len(process.stdout.splitlines()) <= 1
        if process.stdout.strip():
            assert isinstance(json.loads(process.stdout), dict)
    e = adapter.build_envelope({**prompt, "turn_id": "turn-two", "prompt": "Continue"})
    assert [m["text"] for m in e["messages"]] == [prompt["prompt"], stop["last_assistant_message"]]
    assert e["history"]["complete"] is False


def test_failed_assessment_does_not_persist_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("PEA_HISTORY_DB", str(tmp_path / "history.db"))
    payload = dict(hook_event_name="UserPromptSubmit", session_id="s", prompt="Write code")
    def failed(_):
        raise TimeoutError("offline failure")
    assert codex.handle(payload, failed)["decision"] == "block"
    assert codex.build_envelope(payload)["messages"] == []


def test_symlink_store_is_rejected_without_touching_target(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.write_text("unchanged")
    link = tmp_path / "history.db"
    link.symlink_to(target)
    monkeypatch.setenv("PEA_HISTORY_DB", str(link))
    e = codex.build_envelope(dict(hook_event_name="UserPromptSubmit", session_id="s", prompt="x"))
    assert "hook history store unavailable" in e["history"]["collection_errors"]
    assert target.read_text() == "unchanged"


def test_existing_history_schema_is_upgraded_without_losing_dialogue(tmp_path, monkeypatch):
    import sqlite3
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE observed (id INTEGER PRIMARY KEY, host TEXT, session TEXT, role TEXT, text TEXT, truncated INTEGER)")
        conn.execute("INSERT INTO observed VALUES(1,'codex','s','user','Earlier objective',0)")
    monkeypatch.setenv("PEA_HISTORY_DB", str(path))
    e = codex.build_envelope(dict(hook_event_name="UserPromptSubmit", session_id="s", prompt="Continue"))
    assert [m["text"] for m in e["messages"]] == ["Earlier objective"]
    with sqlite3.connect(path) as conn:
        assert "event_key" in {r[1] for r in conn.execute("PRAGMA table_info(observed)")}
