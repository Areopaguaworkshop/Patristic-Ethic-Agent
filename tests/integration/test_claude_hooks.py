"""Offline tests for the PEA Claude Code native adapter (plan §M5).

No network, no Claude Code binary: every test drives build_envelope,
decide, and main directly, or reads the example settings file. Live
behavior claims live in docs/hosts/claude-code.md, not here.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from patristic_ethics.adapters import claude_code

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "examples" / "claude-code" / "settings.json"

EVENTS = ("UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "MessageDisplay")


def payload(event: str, **overrides) -> dict:
    """Common hook payload fields (verified contract) + event overrides."""
    base: dict = {
        "session_id": "sess-123",
        "prompt_id": "prompt-456",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": "/home/user/project",
        "permission_mode": "default",
        "hook_event_name": event,
    }
    if event == "UserPromptSubmit":
        base["prompt"] = "How do I write a regex?"
    if event == "PreToolUse":
        base["tool_name"] = "Bash"
        base["tool_input"] = {"command": "ls -la"}
    if event == "PostToolUse":
        base["tool_name"] = "Bash"
        base["tool_response"] = "file1.py file2.py"
    if event == "Stop":
        base["last_assistant_message"] = "Here is the answer."
    if event == "MessageDisplay":
        base["message"] = {"role": "assistant", "content": "Here is the answer."}
    return {**base, **overrides}


def envelope_for(event: str, **overrides) -> dict:
    """build_envelope with a non-None guarantee (test helper)."""
    env = claude_code.build_envelope(payload(event, **overrides))
    assert env is not None, f"envelope rejected for {event}"
    return env


def decide_out(action: str, event: str, **overrides) -> dict:
    """decide with a non-None guarantee (test helper)."""
    result = {
        "action": action,
        "decision": None,
        "guidance": {"text": "PEA guidance text.", "citations": [],
                     "source_status": "verified", "limited": False},
        "failure": None,
        "audit": {},
    }
    out = claude_code.decide(result, payload(event, **overrides))
    assert out is not None, f"decide returned None for {event}/{action}"
    return out


# --- build_envelope -------------------------------------------------


@pytest.mark.parametrize("event", EVENTS)
def test_build_envelope_valid_per_event(event: str) -> None:
    env = envelope_for(event)
    assert env["host"] == {"name": "claude-code", "version": "2.1.286", "mode": "native"}
    assert env["session"]["id"] == "sess-123"
    assert env["turn"]["id"] == "prompt-456"
    assert env["messages"] == []
    assert env["history"]["complete"] is False  # transcript async — not parsed


@pytest.mark.parametrize("event,stage", [
    ("UserPromptSubmit", "input"),
    ("PreToolUse", "pre_action"),
    ("PostToolUse", "output"),
    ("Stop", "output"),
    ("MessageDisplay", "output"),
])
def test_build_envelope_stage_mapping(event: str, stage: str) -> None:
    assert envelope_for(event)["stage"] == stage


def test_build_envelope_stage_fields() -> None:
    assert envelope_for("UserPromptSubmit")["request"] == "How do I write a regex?"

    env = envelope_for("PreToolUse")
    assert env["request"] == "Tool call: Bash"
    assert env["proposed_action"] == {"tool": "Bash", "arguments": {"command": "ls -la"}}

    assert envelope_for("PostToolUse")["candidate_response"] == "file1.py file2.py"
    assert envelope_for("Stop")["candidate_response"] == "Here is the answer."
    assert envelope_for("MessageDisplay")["candidate_response"] == "Here is the answer."


def test_build_envelope_missing_optional_fields() -> None:
    assert envelope_for("PostToolUse", tool_response=None)["candidate_response"] == ""
    assert envelope_for("Stop", last_assistant_message=None)["candidate_response"] == ""

    env = claude_code.build_envelope(
        {"session_id": "s1", "hook_event_name": "UserPromptSubmit"}
    )
    assert env is not None
    assert env["turn"]["id"].startswith("turn-")
    assert env["request"] == ""

    env = envelope_for("PreToolUse", tool_input=None)
    assert env["proposed_action"]["arguments"] == {}


@pytest.mark.parametrize("garbage", [
    "not a dict",
    {"hook_event_name": "Unknown"},
    {},
    {"session_id": "s1"},  # no hook_event_name -> unmapped event
])
def test_build_envelope_rejects_garbage(garbage) -> None:
    assert claude_code.build_envelope(garbage) is None


# --- decide: event × action table ------------------------------------


@pytest.mark.parametrize("event", EVENTS)
def test_decide_proceed_is_none(event: str) -> None:
    result = {"action": "proceed", "guidance": None}
    assert claude_code.decide(result, payload(event)) is None


# Spec mapping table (event × action) for blocking actions:
# - UserPromptSubmit: refuse/clarify/review/withhold → block
# - PreToolUse:       refuse/clarify/review/withhold → deny
# - PostToolUse/Stop: refuse → block (others → None)
# - MessageDisplay:   refuse → displayContent (clarify/review/withhold → None)
BLOCKING_EVENTS = ("UserPromptSubmit", "PreToolUse")
REFUSE_ONLY_EVENTS = ("PostToolUse", "Stop", "MessageDisplay")


@pytest.mark.parametrize("event", BLOCKING_EVENTS)
@pytest.mark.parametrize("action", ["refuse", "clarify", "review", "withhold"])
def test_decide_blocking_actions(event: str, action: str) -> None:
    out = decide_out(action, event)
    if event == "UserPromptSubmit":
        assert out == {"decision": "block", "reason": "PEA guidance text."}
    else:  # PreToolUse
        hso = out["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny"
        assert hso["permissionDecisionReason"] == "PEA guidance text."
        assert hso["additionalContext"] == "PEA guidance text."


@pytest.mark.parametrize("event", REFUSE_ONLY_EVENTS)
@pytest.mark.parametrize("action", ["clarify", "review", "withhold"])
def test_decide_clarify_review_withhold_none_on_output_events(event: str, action: str) -> None:
    result = {"action": action, "guidance": {"text": "PEA guidance text."}}
    assert claude_code.decide(result, payload(event)) is None


def test_decide_pretooluse_reason_truncated_at_500() -> None:
    result = {
        "action": "refuse",
        "guidance": {"text": "x" * 600, "citations": [], "source_status": "verified", "limited": False},
    }
    out = claude_code.decide(result, payload("PreToolUse"))
    assert out is not None
    hso = out["hookSpecificOutput"]
    assert len(hso["permissionDecisionReason"]) == 500
    assert len(hso["additionalContext"]) == 600  # context keeps full text


@pytest.mark.parametrize("event", EVENTS)
def test_decide_guide(event: str) -> None:
    if event in ("PostToolUse", "Stop"):
        result = {"action": "guide", "guidance": {"text": "PEA guidance text."}}
        assert claude_code.decide(result, payload(event)) is None
        return
    out = decide_out("guide", event)
    hso = out["hookSpecificOutput"]
    if event == "UserPromptSubmit":
        assert hso["hookEventName"] == "UserPromptSubmit"
        assert hso["additionalContext"] == "PEA guidance text."
    elif event == "PreToolUse":
        assert hso["permissionDecision"] == "allow"
        assert hso["additionalContext"] == "PEA guidance text."
    else:  # MessageDisplay: advisory display-only
        assert hso["hookEventName"] == "MessageDisplay"
        assert hso["displayContent"] == "PEA: PEA guidance text."


def test_decide_messagedisplay_guide_refuse_prefix() -> None:
    for action in ("guide", "refuse"):
        hso = decide_out(action, "MessageDisplay")["hookSpecificOutput"]
        assert hso["hookEventName"] == "MessageDisplay"
        assert hso["displayContent"].startswith("PEA: ")


def test_decide_messagedisplay_other_actions_none() -> None:
    for action in ("proceed", "clarify", "review", "withhold"):
        result = {"action": action, "guidance": {"text": "PEA guidance text."}}
        assert claude_code.decide(result, payload("MessageDisplay")) is None


def test_decide_unknown_event_none() -> None:
    result = {"action": "refuse", "guidance": {"text": "PEA guidance text."}}
    assert claude_code.decide(result, {"hook_event_name": "Nope"}) is None


def test_decide_missing_guidance_uses_placeholder() -> None:
    out = claude_code.decide({"action": "refuse", "guidance": None}, payload("Stop"))
    assert out is not None
    assert out["decision"] == "block"
    assert out["reason"] == claude_code._NO_GUIDANCE


# --- handle / main ----------------------------------------------------


def _run_main(monkeypatch, stdin_text: str, runner) -> "tuple[int, str, str]":
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = claude_code.main(runner=runner)
    return code, out.getvalue(), err.getvalue()


def test_main_refuse_prints_single_protocol_line(monkeypatch) -> None:
    def runner(_envelope: str) -> str:
        return json.dumps({"action": "refuse", "guidance": {"text": "PEA guidance text."}})

    code, stdout, stderr = _run_main(
        monkeypatch, json.dumps(payload("UserPromptSubmit")), runner
    )
    assert code == 0
    lines = [l for l in stdout.splitlines() if l.strip()]
    assert len(lines) == 1, "stdout must be exactly one JSON line"
    obj = json.loads(lines[0])
    assert obj["decision"] == "block"
    assert "PEA guidance text." in obj["reason"]
    assert stderr == ""


def test_main_proceed_prints_nothing(monkeypatch) -> None:
    def runner(_envelope: str) -> str:
        return json.dumps({"action": "proceed", "guidance": None})

    code, stdout, _ = _run_main(
        monkeypatch, json.dumps(payload("PreToolUse")), runner
    )
    assert code == 0
    assert stdout == ""


def test_main_malformed_stdin_exit0_empty_stdout(monkeypatch) -> None:
    code, stdout, stderr = _run_main(monkeypatch, "{not json", lambda _e: "")
    assert code == 0
    assert stdout == ""
    assert "malformed" in stderr
    assert "fail-open" in stderr


def test_main_runner_raises_exit0_empty_stdout(monkeypatch) -> None:
    def runner(_envelope: str) -> str:
        raise RuntimeError("cli timeout")

    code, stdout, stderr = _run_main(
        monkeypatch, json.dumps(payload("PreToolUse")), runner
    )
    assert code == 0
    assert stdout == ""
    assert "fail-open" in stderr


def test_main_unmapped_event_fail_open(monkeypatch) -> None:
    code, stdout, stderr = _run_main(
        monkeypatch, json.dumps({"hook_event_name": "SessionEnd"}), lambda _e: ""
    )
    assert code == 0
    assert stdout == ""
    assert "fail-open" in stderr


def test_main_bad_runner_output_fail_open(monkeypatch) -> None:
    code, stdout, stderr = _run_main(
        monkeypatch, json.dumps(payload("Stop")), lambda _e: "not json"
    )
    assert code == 0
    assert stdout == ""
    assert "fail-open" in stderr


def test_handle_proceed_returns_none_without_diag() -> None:
    out, diag = claude_code.handle(
        payload("UserPromptSubmit"),
        lambda _e: json.dumps({"action": "proceed", "guidance": None}),
    )
    assert out is None and diag is None


def test_protocol_purity_no_stdout_logs(monkeypatch) -> None:
    """stdout carries only protocol JSON: every diagnostic goes to stderr."""
    def runner(_envelope: str) -> str:
        return json.dumps({"action": "guide", "guidance": {"text": "PEA guidance text."}})

    code, stdout, stderr = _run_main(
        monkeypatch, json.dumps(payload("UserPromptSubmit")), runner
    )
    assert code == 0
    obj = json.loads(stdout.strip())
    assert obj["hookSpecificOutput"]["additionalContext"] == "PEA guidance text."
    assert stderr == ""


# --- example settings --------------------------------------------------


def test_settings_json_parses() -> None:
    json.loads(SETTINGS.read_text(encoding="utf-8"))


def test_settings_has_both_hook_keys() -> None:
    cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
    hooks = cfg["hooks"]
    assert "UserPromptSubmit" in hooks
    assert "PreToolUse" in hooks


def test_settings_hooks_have_timeouts_and_command() -> None:
    cfg = json.loads(SETTINGS.read_text(encoding="utf-8"))
    for event in ("UserPromptSubmit", "PreToolUse"):
        for entry in cfg["hooks"][event]:
            for hook in entry["hooks"]:
                assert hook["type"] == "command"
                assert "patristic_ethics.adapters.claude_code" in hook["command"]
                assert hook["timeout"] >= 15, "runner timeout is 15s; hook must exceed it"
    assert cfg["hooks"]["PreToolUse"][0]["matcher"] == "Bash"


def test_settings_json_has_no_comments() -> None:
    text = SETTINGS.read_text(encoding="utf-8")
    for line in text.splitlines():
        assert not line.lstrip().startswith("//"), "settings.json must be comment-free"