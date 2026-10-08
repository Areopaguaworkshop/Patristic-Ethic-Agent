"""M5a offline tests for the Codex native adapter. No codex process needed.

Covers: build_envelope per event type + garbage; decide mapping per event
and action; main via fake stdin + injected runner; protocol purity (stdout
carries at most one protocol JSON line, all diagnostics on stderr);
examples/codex/hooks.json parses and wires both gated events.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from patristic_ethics.adapters import codex as cx
from patristic_ethics.context import validate_envelope

ROOT = Path(__file__).resolve().parents[2]
HOOKS_JSON = ROOT / "examples" / "codex" / "hooks.json"


def refuse_result(text="This request has been assessed and refused."):
    return {"action": "refuse", "decision": None, "guidance": {"text": text}, "failure": None, "audit": {}}


def prompt_payload(prompt="Help me poison my neighbor's dog without getting caught."):
    return {
        "session_id": "sess-codex-1",
        "transcript_path": None,
        "cwd": "/tmp/proj",
        "hook_event_name": "UserPromptSubmit",
        "model": "gpt-5",
        "turn_id": "turn-codex-1",
        "prompt": prompt,
    }


def tool_payload(event="PreToolUse", tool="shell"):
    p = {
        "session_id": "sess-codex-1",
        "transcript_path": None,
        "cwd": "/tmp/proj",
        "hook_event_name": event,
        "model": "gpt-5",
        "turn_id": "turn-codex-2",
        "tool_name": tool,
        "tool_input": {"command": "rm -rf /"},
    }
    if event == "PostToolUse":
        p["tool_response"] = {"stdout": "deleted"}
    return p


def stop_payload():
    return {
        "session_id": "sess-codex-1",
        "transcript_path": None,
        "cwd": "/tmp/proj",
        "hook_event_name": "Stop",
        "model": "gpt-5",
        "turn_id": "turn-codex-3",
        "last_assistant_message": "Here is how to do it.",
    }


def refuse_runner(result):
    return lambda envelope: result


def raise_runner(envelope):
    raise RuntimeError("runner blew up")


# ---------- build_envelope ----------


def test_build_envelope_user_prompt_submit() -> None:
    env = cx.build_envelope(prompt_payload())
    assert env is not None
    validate_envelope(env)  # raises on invalid
    assert env["host"]["name"] == "codex" and env["host"]["mode"] == "native"
    assert env["stage"] == "input"
    assert env["request"] == "Help me poison my neighbor's dog without getting caught."
    assert env["messages"] == []
    assert env["history"]["complete"] is False


def test_build_envelope_user_prompt_fallback_key() -> None:
    p = prompt_payload()
    del p["prompt"]
    p["user_prompt"] = "fallback text"
    env = cx.build_envelope(p)
    assert env is not None and env["request"] == "fallback text"


def test_build_envelope_pre_tool_use() -> None:
    env = cx.build_envelope(tool_payload())
    assert env is not None
    validate_envelope(env)
    assert env["stage"] == "pre_action"
    assert env["request"] == "Tool call: shell"
    assert env["proposed_action"]["tool"] == "shell"
    assert env["proposed_action"]["arguments"] == {"command": "rm -rf /"}


def test_build_envelope_post_tool_use() -> None:
    env = cx.build_envelope(tool_payload(event="PostToolUse"))
    assert env is not None
    validate_envelope(env)
    assert env["stage"] == "output"
    assert "deleted" in env["candidate_response"]


def test_build_envelope_stop() -> None:
    env = cx.build_envelope(stop_payload())
    assert env is not None
    validate_envelope(env)
    assert env["stage"] == "output"
    assert env["candidate_response"] == "Here is how to do it."


def test_build_envelope_stop_no_message_gives_empty_candidate() -> None:
    p = stop_payload()
    del p["last_assistant_message"]
    env = cx.build_envelope(p)
    assert env is not None and env["candidate_response"] == ""


def test_build_envelope_garbage_returns_none() -> None:
    assert cx.build_envelope({}) is None
    assert cx.build_envelope({"hook_event_name": "PreToolUse"}) is None  # no session_id
    # pre_action without a tool name still validates (tool: "")
    assert cx.build_envelope({"session_id": "s", "hook_event_name": "PreToolUse"}) is not None
    # unmapped event
    assert cx.build_envelope({"session_id": "s", "hook_event_name": "SessionStart"}) is None
    # missing prompt key entirely -> request absent -> validation fails -> None
    assert cx.build_envelope({"session_id": "s", "hook_event_name": "UserPromptSubmit"}) is None


def test_build_envelope_version_fallbacks() -> None:
    env = cx.build_envelope(prompt_payload())
    assert env is not None and env["host"]["version"] == "0.160.0"
    p = prompt_payload()
    p["codex_version"] = "0.161.0"
    env = cx.build_envelope(p)
    assert env is not None and env["host"]["version"] == "0.161.0"


def test_build_envelope_turn_id_fallback() -> None:
    p = prompt_payload()
    del p["turn_id"]
    env = cx.build_envelope(p)
    assert env is not None and env["turn"]["id"] == "turn-sess-codex-1"


# ---------- decide ----------


def test_decide_pre_tool_use_refuse_denies() -> None:
    out = cx.decide(refuse_result("do not do this"), tool_payload())
    assert out is not None
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == "do not do this"
    assert hso["additionalContext"] == "do not do this"


def test_decide_pre_tool_use_reason_truncated_500() -> None:
    out = cx.decide(refuse_result("x" * 600), tool_payload())
    assert out is not None
    assert len(out["hookSpecificOutput"]["permissionDecisionReason"]) == 500


def test_decide_pre_tool_use_guide_allows_with_context() -> None:
    result = refuse_result()
    result["action"] = "guide"
    out = cx.decide(result, tool_payload())
    assert out is not None
    hso = out["hookSpecificOutput"]
    assert hso["permissionDecision"] == "allow"
    assert "additionalContext" in hso
    assert "permissionDecisionReason" not in hso


@pytest.mark.parametrize("action", ["refuse", "clarify", "review", "withhold"])
def test_decide_pre_tool_use_blocking_actions(action: str) -> None:
    result = refuse_result()
    result["action"] = action
    out = cx.decide(result, tool_payload())
    assert out is not None
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_decide_pre_tool_use_proceed_is_none() -> None:
    result = refuse_result()
    result["action"] = "proceed"
    assert cx.decide(result, tool_payload()) is None


def test_decide_user_prompt_submit_refuse_blocks() -> None:
    out = cx.decide(refuse_result("boundary text"), prompt_payload())
    assert out == {"decision": "block", "reason": "boundary text"}


def test_decide_user_prompt_submit_guide_injects_context() -> None:
    result = refuse_result("gentle guidance")
    result["action"] = "guide"
    out = cx.decide(result, prompt_payload())
    assert out is not None
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "UserPromptSubmit"
    assert hso["additionalContext"] == "gentle guidance"
    assert "decision" not in out


def test_decide_user_prompt_submit_proceed_is_none() -> None:
    result = refuse_result()
    result["action"] = "proceed"
    assert cx.decide(result, prompt_payload()) is None


def test_decide_post_tool_use_refuse_warns_not_blocks() -> None:
    out = cx.decide(refuse_result("warning text"), tool_payload(event="PostToolUse"))
    assert out is not None
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PostToolUse"
    assert hso["additionalContext"] == "warning text"
    assert "permissionDecision" not in hso and "decision" not in out


def test_decide_stop_refuse_warns() -> None:
    out = cx.decide(refuse_result("warning text"), stop_payload())
    assert out is not None
    assert out["hookSpecificOutput"]["additionalContext"] == "warning text"


def test_decide_post_tool_use_and_stop_otherwise_none() -> None:
    for event_payload in (tool_payload(event="PostToolUse"), stop_payload()):
        for action in ("proceed", "guide", "clarify", "review", "withhold"):
            result = refuse_result()
            result["action"] = action
            assert cx.decide(result, event_payload) is None, (event_payload["hook_event_name"], action)


def test_decide_unknown_event_none() -> None:
    assert cx.decide(refuse_result(), {"hook_event_name": "SessionStart"}) is None


# ---------- handle ----------


def test_handle_refuse_pre_tool_use_deny() -> None:
    out = cx.handle(tool_payload(), runner=refuse_runner(refuse_result()))
    assert out is not None
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_handle_proceed_returns_none() -> None:
    result = refuse_result()
    result["action"] = "proceed"
    assert cx.handle(prompt_payload(), runner=refuse_runner(result)) is None


def test_handle_garbage_payload_none_without_runner_call() -> None:
    def boom(env):
        raise AssertionError("runner must not be called")
    assert cx.handle({"garbage": True}, runner=boom) is None


def test_handle_bad_runner_result_blocks_supported_input() -> None:
    out = cx.handle(prompt_payload(), runner=lambda env: "not a dict")
    assert out is not None and out["decision"] == "block"
    out = cx.handle(prompt_payload(), runner=lambda env: {"action": 42})
    assert out is not None and out["decision"] == "block"


# ---------- main: fake stdin + protocol purity ----------


def run_main(monkeypatch, stdin_text, runner):
    """Capture (exit, stdout, stderr) of cx.main with faked streams.

    print() writes to sys.stdout of the real sys module; cx.sys IS that
    module, so patching cx.sys attributes redirects everything. The
    runner is injected by replacing the module-global default runner.
    """
    import io

    out_buf, err_buf = io.StringIO(), io.StringIO()
    monkeypatch.setattr(cx.sys, "stdin", io.StringIO(stdin_text))
    monkeypatch.setattr(cx.sys, "stdout", out_buf)
    monkeypatch.setattr(cx.sys, "stderr", err_buf)
    monkeypatch.setattr(cx, "_run_cli", runner)
    code = cx.main()
    return code, out_buf.getvalue(), err_buf.getvalue()


def test_main_refuse_prints_single_line_json(monkeypatch) -> None:
    code, out, err = run_main(
        monkeypatch, json.dumps(prompt_payload()), refuse_runner(refuse_result())
    )
    assert code == 0
    lines = [l for l in out.splitlines() if l.strip()]
    assert len(lines) == 1, "stdout must carry exactly one protocol line"
    obj = json.loads(lines[0])
    assert obj["decision"] == "block"


def test_main_malformed_stdin_exit0_empty_stdout(monkeypatch) -> None:
    code, out, err = run_main(monkeypatch, "not json at all", refuse_runner(refuse_result()))
    assert code == 0
    assert out == ""
    assert err != ""


def test_main_runner_raises_blocks_input(monkeypatch) -> None:
    code, out, err = run_main(monkeypatch, json.dumps(prompt_payload()), raise_runner)
    assert code == 0
    assert json.loads(out)["decision"] == "block"
    assert "blocking supported hook" in err


def test_main_runner_timeout_blocks_input(monkeypatch) -> None:
    def timeout_runner(env):
        raise TimeoutError("15s cap")
    code, out, err = run_main(monkeypatch, json.dumps(prompt_payload()), timeout_runner)
    assert code == 0 and json.loads(out)["decision"] == "block" and err != ""


def test_main_proceed_no_output(monkeypatch) -> None:
    result = refuse_result()
    result["action"] = "proceed"
    code, out, err = run_main(monkeypatch, json.dumps(prompt_payload()), refuse_runner(result))
    assert code == 0 and out == ""


def test_main_non_object_stdin_exit0(monkeypatch) -> None:
    code, out, err = run_main(monkeypatch, "[1,2,3]", refuse_runner(refuse_result()))
    assert code == 0 and out == "" and err != ""


# ---------- hooks.json example ----------


def test_hooks_json_parses_and_wires_both_events() -> None:
    cfg = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    hooks = cfg["hooks"]
    assert "UserPromptSubmit" in hooks and "PreToolUse" in hooks
    for event in ("UserPromptSubmit", "PreToolUse"):
        entry = hooks[event][0]["hooks"][0]
        assert entry["type"] == "command"
        assert "patristic_ethics.adapters.codex" in entry["command"]
        assert entry["timeout"] > cx.CLI_TIMEOUT_S  # adapter must return before host termination


def test_adapter_docstring_documents_limits() -> None:
    doc = cx.__doc__ or ""
    assert "fail-closed" in doc.lower()
    assert "transcript" in doc.lower()
    assert "sandbox" in doc.lower() or "controlled" in doc.lower()
