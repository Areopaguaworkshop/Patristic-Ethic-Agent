"""Offline tests for the PEA-controlled OpenCode client (M4b).

All tests use fake runner/assessor callables; no live `opencode`, no
network, nothing written to disk by the client.
"""

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from patristic_ethics.assess import AssessResult
from patristic_ethics.controlled import (
    CONTROLLED_CONFIG,
    HostOutput,
    ControlledClient,
    WITHHELD_MESSAGE,
    controlled_profile_error,
    _parser,
    main,
    parse_host_stdout,
)
from patristic_ethics.context import build_envelope
from patristic_ethics.guidance import GuidanceResult

MODULE_SRC = Path(__file__).parent.parent / "src" / "patristic_ethics" / "controlled.py"


def _res(action, text=None):
    decision = SimpleNamespace(disposition="allow") if action == "proceed" else None
    return AssessResult(
        action=action,
        decision=decision,
        guidance=GuidanceResult(text=text if text is not None else f"PEA-{action}-text"),
    )


def _client(runner, in_res, out_res=None):
    calls = {"runner": 0, "assessor": []}

    def assessor(envelope):
        calls["assessor"].append(envelope)
        if envelope.stage == "input":
            return in_res
        assert out_res is not None, "host ran but no output assessment scripted"
        return out_res

    def r(prompt, session_id=None):
        calls["runner"] += 1
        return runner(prompt, session_id=session_id) if session_id else runner(prompt)

    return ControlledClient(runner=r, assessor=assessor), calls


def _json_line(obj, **over):
    part = {"id": "p1", "messageID": "m1", "sessionID": "s1", "type": "text", "text": "x"}
    part.update(over)
    return {"type": "text", "timestamp": 1, "sessionID": "s1", "part": part}


# --- parse_host_stdout ---


def test_parse_host_stdout_concatenates_three_text_parts_in_order():
    lines = "\n".join(
        json_dumps(part_text)
        for part_text in ("alpha ", "beta ", "gamma")
    )
    out = parse_host_stdout(lines)
    assert out.text == "alpha beta gamma"
    assert out.failure is None


def json_dumps(text):
    import json

    return json.dumps(_json_line(None, text=text))


def test_parse_host_stdout_ignores_non_text_events():
    lines = '{"type":"step-start","sessionID":"s1"}\n' + json_dumps("kept")
    out = parse_host_stdout(lines)
    assert out.text == "kept"
    assert out.failure is None


def test_parse_host_stdout_non_json_line_is_failure():
    out = parse_host_stdout("not json\n" + json_dumps("secret"))
    assert out.failure is not None
    assert out.text == ""


def test_parse_host_stdout_rejects_mixed_session_ids():
    lines = '{"type":"step-start","sessionID":"s1"}\n' + json.dumps(
        {"type": "step-start", "sessionID": "s2"}
    )
    out = parse_host_stdout(lines)
    assert out.failure == "stdout contains multiple OpenCode sessions"


def test_resolved_profile_must_deny_all_tools_and_mcp():
    safe = json.dumps(CONTROLLED_CONFIG)
    assert controlled_profile_error(safe) is None

    enabled = json.loads(safe)
    enabled["permission"]["bash"] = "allow"
    assert "not deny-all" in controlled_profile_error(json.dumps(enabled))

    enabled = json.loads(safe)
    enabled["agent"]["pea-controlled"]["tools"]["bash"] = True
    assert "enables" in controlled_profile_error(json.dumps(enabled))

    enabled = json.loads(safe)
    enabled["mcp"]["external"] = {"type": "local", "command": ["x"]}
    assert "MCP servers" in controlled_profile_error(json.dumps(enabled))


def test_controlled_client_resumes_only_previously_released_turns():
    seen = []

    def runner(prompt, session_id=None):
        seen.append((prompt, session_id))
        return HostOutput(text=f"answer to {prompt}", session_id="host-session")

    client, calls = _client(
        runner=runner,
        in_res=_res("proceed"),
        out_res=_res("proceed"),
    )
    first = client.run("first request")
    second = client.run("follow-up")

    assert seen == [("first request", None), ("follow-up", "host-session")]
    assert second.audit["session"] == first.audit["session"]
    second_input = [e for e in calls["assessor"] if e.stage == "input"][1]
    assert second_input.history.complete is True
    assert [(m.role, m.text) for m in second_input.messages] == [
        ("user", "first request"),
        ("assistant", "answer to first request"),
    ]


def test_replaced_output_is_not_retained_for_a_later_turn():
    seen = []
    prompts = []

    def runner(prompt, session_id=None):
        seen.append(session_id)
        prompts.append(prompt)
        return HostOutput(text="replaced candidate", session_id="host-session")

    client, calls = _client(
        runner=runner,
        in_res=_res("proceed"),
        out_res=_res("guide", "PEA guidance"),
    )
    client.run("first")
    client.run("second")

    inputs = [e for e in calls["assessor"] if e.stage == "input"]
    assert seen == [None, None]
    assert [(m.role, m.text) for m in inputs[1].messages] == [
        ("user", "first"),
        ("assistant", "PEA guidance"),
    ]
    assert "replaced candidate" not in prompts[1]
    assert "PEA guidance" in prompts[1]
    assert inputs[1].history.complete is True


def test_a_different_session_id_cannot_reuse_prior_dialogue():
    seen = []

    def runner(prompt, session_id=None):
        seen.append(session_id)
        return HostOutput(text="answer", session_id=f"host-{len(seen)}")

    client, calls = _client(
        runner=runner,
        in_res=_res("proceed"),
        out_res=_res("proceed"),
    )
    client.run("private first session", session_id="session-a")
    client.run("new session", session_id="session-b")

    inputs = [e for e in calls["assessor"] if e.stage == "input"]
    assert seen == [None, None]
    assert inputs[1].messages == []
    assert inputs[1].session.id == "session-b"


def test_opencode_runner_forces_tools_off_over_inherited_config(monkeypatch):
    import json
    import subprocess
    import patristic_ethics.controlled as controlled

    captured = {}
    commands = []

    def fake_run(argv, **kwargs):
        commands.append(argv)
        captured.update(kwargs)
        stdout = json.dumps(CONTROLLED_CONFIG) if "debug" in argv else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", '{"permission":{"*":"allow"}}')
    monkeypatch.setattr(controlled.subprocess, "run", fake_run)
    controlled.opencode_runner("hello", workdir=".", model="test/model")

    config = json.loads(captured["env"]["OPENCODE_CONFIG_CONTENT"])
    assert config == CONTROLLED_CONFIG
    assert config["permission"]["*"] == "deny"
    assert config["agent"]["pea-controlled"]["tools"]["*"] is False
    assert config["plugin"] == []
    assert commands[0] == ["opencode", "debug", "config", "--pure"]
    assert "--pure" in commands[1]
    assert commands[1][commands[1].index("--agent") + 1] == "pea-controlled"


def test_opencode_runner_resumes_the_session_it_was_given(monkeypatch):
    import subprocess
    import patristic_ethics.controlled as controlled

    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        stdout = json.dumps(CONTROLLED_CONFIG) if "debug" in argv else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(controlled.subprocess, "run", fake_run)
    controlled.opencode_runner(
        "follow-up", workdir=".", model="test/model", session_id="session-1"
    )
    assert captured["argv"][captured["argv"].index("--session") + 1] == "session-1"


def test_opencode_runner_never_launches_when_resolved_policy_allows_a_tool(monkeypatch):
    import subprocess
    import patristic_ethics.controlled as controlled

    commands = []
    config = json.loads(json.dumps(CONTROLLED_CONFIG))
    config["permission"]["bash"] = "allow"

    def fake_run(argv, **kwargs):
        commands.append(argv)
        stdout = json.dumps(config) if "debug" in argv else ""
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(controlled.subprocess, "run", fake_run)
    out = controlled.opencode_runner("do work", workdir=".", model="test/model")
    assert out.failure == "OpenCode resolved permissions are not deny-all"
    assert len(commands) == 1
    assert commands[0][:3] == ["opencode", "debug", "config"]


# --- input gate: host never invoked ---


def test_input_refuse_blocks_host():
    client, calls = _client(
        runner=lambda p: HostOutput(text="SHOULD NOT APPEAR"),
        in_res=_res("refuse", "PEA boundary: this assistance is refused."),
    )
    result = client.run("harmful prompt")
    assert calls["runner"] == 0
    assert result.model_invoked is False
    assert "PEA boundary" in result.released_text
    assert result.action == "refuse"
    assert result.output_assessment is None
    assert result.buffered == ""
    assert result.audit["buffered_chars"] == 0


def test_input_clarify_blocks_host_with_question():
    client, calls = _client(
        runner=lambda p: HostOutput(text="leak"),
        in_res=_res("clarify", "PEA question: which target do you mean?"),
    )
    result = client.run("ambiguous prompt")
    assert calls["runner"] == 0
    assert "PEA question" in result.released_text
    assert result.model_invoked is False


def test_input_review_blocks_host_with_pause():
    client, calls = _client(
        runner=lambda p: HostOutput(text="leak"),
        in_res=_res("review", "PEA pause: this needs human review."),
    )
    result = client.run("ambiguous harmful prompt")
    assert calls["runner"] == 0
    assert "PEA pause" in result.released_text
    assert result.model_invoked is False


def test_input_withhold_blocks_host():
    client, calls = _client(
        runner=lambda p: HostOutput(text="leak"),
        in_res=_res("withhold", text=""),
    )
    result = client.run("any")
    assert calls["runner"] == 0
    assert result.released_text == WITHHELD_MESSAGE


# --- input allow: host runs, output gate decides ---


def test_allow_and_output_proceed_releases_buffered_concatenation():
    parts = ["Answer part one. ", "Answer part two. ", "Answer part three."]
    def runner(prompt):
        return HostOutput(text="".join(parts))

    client, calls = _client(runner=runner, in_res=_res("proceed"), out_res=_res("proceed"))
    result = client.run("How do I kill a process on Linux?")
    assert calls["runner"] == 1
    assert result.model_invoked is True
    assert result.released_text == "".join(parts)
    assert result.buffered == "".join(parts)
    assert result.audit["released_chars"] == len(result.buffered) > 0
    stages = [e.stage for e in calls["assessor"]]
    assert stages == ["input", "output"]
    out_env = calls["assessor"][1]
    assert out_env.candidate_response == "".join(parts)
    in_env = calls["assessor"][0]
    assert in_env.history.complete is True
    assert in_env.messages == []


def test_allowed_candidate_with_unverified_patristic_quote_is_withheld():
    client, _ = _client(
        runner=lambda prompt: HostOutput(
            text='Augustine said "The moon is made of cheese."'
        ),
        in_res=_res("proceed"),
        out_res=_res("proceed"),
    )
    result = client.run("What did Augustine teach?")
    assert result.action == "withhold"
    assert result.released_text == WITHHELD_MESSAGE
    assert "moon is made of cheese" not in result.released_text


def test_any_failed_output_check_withholds_even_if_action_says_proceed():
    mismatched_assessment = AssessResult(
        action="proceed",
        decision=SimpleNamespace(disposition="refuse"),
        guidance=GuidanceResult(text="PEA refusal guidance"),
    )
    client, _ = _client(
        runner=lambda prompt: HostOutput(text="Instructions to poison someone."),
        in_res=_res("proceed"),
        out_res=mismatched_assessment,
    )
    result = client.run("explain safe chemistry")
    assert result.action == "withhold"
    assert result.released_text == WITHHELD_MESSAGE
    assert "Instructions to poison" not in result.released_text
    assert result.failure == "assessment failed: ValueError"


def test_output_refuse_replaces_with_guidance_buffer_discarded():
    client, _ = _client(
        runner=lambda p: HostOutput(text="prohibited answer content"),
        in_res=_res("proceed"),
        out_res=_res("refuse", "PEA refuse guidance with an alternative."),
    )
    result = client.run("harmful")
    assert result.action == "refuse"
    assert result.released_text == "PEA refuse guidance with an alternative."
    assert "prohibited answer content" not in result.released_text
    assert result.buffered == "prohibited answer content"  # audit-only, in memory
    assert result.audit["released_chars"] != result.audit["buffered_chars"]


def test_output_withhold_replaces_with_static_message():
    client, _ = _client(
        runner=lambda p: HostOutput(text="candidate"),
        in_res=_res("proceed"),
        out_res=_res("withhold", text=""),
    )
    result = client.run("x")
    assert result.released_text == WITHHELD_MESSAGE
    assert result.buffered == "candidate"


def test_output_guide_replaces_with_guidance():
    client, _ = _client(
        runner=lambda p: HostOutput(text="raw"),
        in_res=_res("proceed"),
        out_res=_res("guide", "PEA guide text."),
    )
    result = client.run("x")
    assert result.released_text == "PEA guide text."
    assert result.buffered == "raw"


# --- executor failure ---


def test_runner_raises_withholds_and_keeps_input_allow():
    def bad_runner(prompt):
        raise RuntimeError("UNREVIEWED_CANDIDATE_MARKER")

    client, calls = _client(runner=bad_runner, in_res=_res("proceed"))
    result = client.run("x")
    assert result.model_invoked is True
    assert result.action == "withhold"
    assert result.released_text == WITHHELD_MESSAGE
    assert result.failure == "host runner raised RuntimeError"
    assert "UNREVIEWED_CANDIDATE_MARKER" not in result.released_text
    assert result.input_assessment.action == "proceed"
    assert result.output_assessment is None


def test_runner_timeout_failure_withholds():
    client, _ = _client(
        runner=lambda p: HostOutput(failure="opencode run timed out after 10s"),
        in_res=_res("proceed"),
    )
    result = client.run("x")
    assert result.released_text == WITHHELD_MESSAGE
    assert "timed out" in result.failure


# --- audit ---


def test_audit_fields_and_stable_prompt_digest():
    client, _ = _client(
        runner=lambda p: HostOutput(text="abc"),
        in_res=_res("proceed"),
        out_res=_res("proceed"),
    )
    r1 = client.run("stable prompt")
    r2 = client.run("stable prompt")
    for key in (
        "session", "prompt_digest", "policy_version", "corpus_version",
        "buffered_chars", "released_chars",
    ):
        assert key in r1.audit
    assert r1.audit["prompt_digest"] == r2.audit["prompt_digest"]
    assert r1.audit["buffered_chars"] == 3
    assert r1.audit["released_chars"] == 3
    assert r1.audit["session"] == r2.audit["session"]


# --- CLI wrapper ---


def test_main_prints_exactly_one_stdout_line_and_exits_zero(monkeypatch, capsys):
    def fake_assessor(envelope):
        if envelope.stage == "input":
            return _res("proceed")
        return _res("proceed")

    monkeypatch.setattr(
        "patristic_ethics.controlled.ControlledClient.__init__",
        lambda self, **kw: _patch_init(self, fake_assessor),
    )
    rc = main(["--prompt", "How do I kill a process on Linux?", "--model", "ollama/x"])
    assert rc == 0
    out = capsys.readouterr()
    lines = [l for l in out.out.splitlines() if l.strip()]
    assert len(lines) == 1
    assert lines[0] == "one two three"
    import json as _json
    diag = _json.loads(out.err.splitlines()[-1])
    assert diag["action"] == "proceed"
    assert diag["model_invoked"] is True
    assert diag["audit"]["released_chars"] == 13


def _patch_init(self, assessor):
    import patristic_ethics.controlled as mod

    self.policy_version = "test"
    self.corpus_version = mod.DEFAULT_CORPUS_VERSION
    self.runner = lambda prompt, session_id=None: HostOutput(text="one two three")
    self.assessor = assessor
    self._controlled_session_id = None
    self._host_session_id = None
    self._visible_history = []


def test_main_setup_failure_exits_one(monkeypatch, capsys):
    def boom(**kw):
        raise RuntimeError("no policy here")

    monkeypatch.setattr("patristic_ethics.controlled.load_policy", boom)
    rc = main(["--prompt", "x", "--model", "ollama/x"])
    assert rc == 1
    out = capsys.readouterr()
    assert "setup failed" in out.err
    assert not out.out.strip()


# --- heuristic: buffered content is never written to disk by this module ---


def test_module_source_has_no_file_write_of_buffered_content():
    """Heuristic source scan: controlled.py must not open() in write mode
    (buffered text stays in memory only)."""
    src = MODULE_SRC.read_text(encoding="utf-8")
    assert "open(" not in src.replace("opencode(", "").replace(
        "parse_host_stdout(", ""
    ), "controlled.py must not open() files (buffered text is in-memory only)"
    for mode in ("'w'", '"w"', "'a'", '"a"'):
        assert mode not in src, f"write mode {mode} found in controlled.py"


def test_parser_requires_prompt_and_model():
    with pytest.raises(SystemExit):
        main(["--model", "m"])
    with pytest.raises(SystemExit):
        _parser().parse_args(["--prompt", "x"])
    args = _parser().parse_args(["--prompt", "x", "--model", "m"])
    assert args.backend == "fake"
    interactive = _parser().parse_args(["--interactive", "--model", "m"])
    assert interactive.interactive is True


def test_interactive_cli_gates_each_turn_and_keeps_diagnostics_off_stdout(monkeypatch, capsys):
    def fake_assessor(envelope):
        return _res("proceed")

    monkeypatch.setattr(
        "patristic_ethics.controlled.ControlledClient.__init__",
        lambda self, **kw: _patch_init(self, fake_assessor),
    )
    monkeypatch.setattr("sys.stdin", io.StringIO("hello\n/quit\n"))
    rc = main(["--interactive", "--model", "ollama/x"])
    assert rc == 0
    out = capsys.readouterr()
    assert out.out.splitlines() == ["one two three"]
    assert "you>" in out.err


@pytest.mark.parametrize("stage", ["input", "output"])
@pytest.mark.parametrize("fault", ["exception", "missing", "unknown-action", "failure-proceed"])
def test_unexpected_assessor_failure_withholds_and_recovers(stage, fault):
    calls = []
    fail = True
    marker = "UNREVIEWED_CANDIDATE_MARKER"

    def assessor(envelope):
        if fail and envelope.stage == stage:
            if fault == "exception":
                raise RuntimeError(marker)
            if fault == "missing":
                return None
            if fault == "failure-proceed":
                from patristic_ethics.interpreter import InterpreterFailure
                return AssessResult(action="proceed", failure=InterpreterFailure(reason=marker))
            return AssessResult(action="invalid")
        return AssessResult(action="proceed", decision=SimpleNamespace(disposition="allow"))

    def runner(prompt, session_id=None):
        calls.append((prompt, session_id))
        return HostOutput(text=marker, session_id="host-session")

    client = ControlledClient(runner=runner, assessor=assessor)
    result = client.run("hello")
    assert result.action == "withhold"
    assert result.released_text == WITHHELD_MESSAGE
    assert result.model_invoked is (stage == "output")
    assert len(calls) == (1 if stage == "output" else 0)
    assert result.failure == "assessment failed: " + ("RuntimeError" if fault == "exception" else "ValueError")
    assert marker not in result.failure
    assert marker not in json.dumps(client._visible_history)
    assert client._host_session_id is None
    fail = False
    recovered = client.run("next")
    assert recovered.action == "proceed"
    assert recovered.released_text == marker
    assert calls[-1][1] is None


def test_validate_result_requires_allow_decision_for_proceed():
    from patristic_ethics.adapters.result import validate_result

    with pytest.raises(ValueError, match="proceed requires an allow decision"):
        validate_result({"action": "proceed"})
    with pytest.raises(ValueError, match="proceed requires an allow decision"):
        validate_result({"action": "proceed", "decision": None})
    assert validate_result(
        {"action": "proceed", "decision": {"disposition": "allow"}}
    )["action"] == "proceed"


def test_controlled_proceed_without_allow_decision_withholds():
    client = ControlledClient(
        assessor=lambda envelope: AssessResult(action="proceed"),
        runner=lambda prompt, session_id=None: HostOutput(text="unreviewed"),
    )
    result = client.run("hello")
    assert result.action == "withhold"
    assert result.released_text == WITHHELD_MESSAGE
