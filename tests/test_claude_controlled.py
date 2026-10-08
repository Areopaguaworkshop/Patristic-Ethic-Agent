import json
from types import SimpleNamespace

from patristic_ethics.assess import AssessResult
from patristic_ethics.claude_controlled import claude_runner, parse_claude_stdout
from patristic_ethics.controlled import ControlledClient, HostOutput
from patristic_ethics.guidance import GuidanceResult


def test_parse_claude_stdout_accepts_only_success_result():
    out = parse_claude_stdout(json.dumps({
        "type": "result", "subtype": "success", "is_error": False,
        "result": "reviewed answer",
    }))
    assert out == HostOutput(text="reviewed answer")
    assert parse_claude_stdout("partial reviewed answer").failure
    assert parse_claude_stdout(json.dumps({
        "type": "result", "is_error": True, "result": "untrusted",
    })).failure


def test_claude_runner_disables_tools_mcp_hooks_and_persistence(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(command=command, **kwargs)
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "buffered"}),
            stderr="",
        )

    monkeypatch.setattr("patristic_ethics.claude_controlled.subprocess.run", fake_run)
    out = claude_runner("prompt", workdir="/tmp/work", executable="claude-test")
    assert out.text == "buffered"
    assert seen["input"] == "prompt"
    assert seen["cwd"] == "/tmp/work"
    command = seen["command"]
    assert "--safe-mode" in command
    assert "--append-system-prompt" in command
    assert command[command.index("--append-system-prompt") + 1]
    assert "--no-session-persistence" in command
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--mcp-config") + 1] == "{}"
    assert "--strict-mcp-config" in command


def test_claude_controlled_client_blocks_input_and_keeps_released_history():
    calls = []

    def assessor(envelope):
        calls.append(envelope)
        if envelope.request == "harmful":
            return AssessResult(action="refuse", guidance=GuidanceResult(text="PEA refused"))
        return AssessResult(action="proceed", guidance=GuidanceResult(text=""))

    prompts = []

    def runner(prompt, session_id=None):
        prompts.append((prompt, session_id))
        return HostOutput(text="safe answer")

    client = ControlledClient(
        runner=runner, assessor=assessor, host_name="claude-code", host_version="2.1.287"
    )
    blocked = client.run("harmful")
    assert blocked.model_invoked is False
    assert prompts == []
    assert blocked.released_text == "PEA refused"

    client.run("first")
    second = client.run("follow-up")
    assert second.released_text == "safe answer"
    host_context = json.loads(prompts[1][0])
    assert host_context["type"] == "pea_conversation_context"
    assert host_context["current_user_request"] == "follow-up"
    assert host_context["prior_released_messages"][-1] == {
        "role": "assistant", "text": "safe answer"
    }
    assert prompts[1][1] is None
    follow_up = calls[3]
    assert follow_up.host.name == "claude-code"
    assert follow_up.history.complete is True
    assert [message.text for message in follow_up.messages] == [
        "harmful", "PEA refused", "first", "safe answer"
    ]


def test_claude_candidate_is_replaced_before_release():
    def assessor(envelope):
        if envelope.stage == "input":
            return AssessResult(action="proceed", guidance=GuidanceResult(text=""))
        return AssessResult(action="refuse", guidance=GuidanceResult(text="PEA refusal"))

    client = ControlledClient(
        runner=lambda *_a, **_k: HostOutput(text="unreleased candidate"),
        assessor=assessor,
        host_name="claude-code",
        host_version="2.1.287",
    )
    result = client.run("ask")
    assert result.buffered == "unreleased candidate"
    assert result.released_text == "PEA refusal"
    assert result.released_text != result.buffered


def test_claude_runner_fails_closed_on_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        "patristic_ethics.claude_controlled.subprocess.run",
        lambda *_a, **_k: SimpleNamespace(returncode=2, stdout="unreleased", stderr="sensitive candidate"),
    )
    out = claude_runner("prompt", workdir=".")
    assert out.failure.startswith("Claude Code exited 2")
    assert "sensitive candidate" not in out.failure
