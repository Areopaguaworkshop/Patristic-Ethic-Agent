"""Offline tests for the PEA-controlled OpenCode client (M4b).

All tests use fake runner/assessor callables; no live `opencode`, no
network, nothing written to disk by the client.
"""

import io
from pathlib import Path

import pytest

from patristic_ethics.assess import AssessResult
from patristic_ethics.controlled import (
    HostOutput,
    ControlledClient,
    WITHHELD_MESSAGE,
    _parser,
    main,
    parse_host_stdout,
)
from patristic_ethics.context import build_envelope
from patristic_ethics.guidance import GuidanceResult

MODULE_SRC = Path(__file__).parent.parent / "src" / "patristic_ethics" / "controlled.py"


def _res(action, text=None):
    return AssessResult(
        action=action,
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

    def r(prompt):
        calls["runner"] += 1
        return runner(prompt)

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
    assert in_env.history.complete is False
    assert "fresh session" in in_env.history.collection_errors


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
        raise RuntimeError("boom")

    client, calls = _client(runner=bad_runner, in_res=_res("proceed"))
    result = client.run("x")
    assert result.model_invoked is True
    assert result.action == "withhold"
    assert result.released_text == WITHHELD_MESSAGE
    assert result.failure and "boom" in result.failure
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
    assert r1.audit["session"] != r2.audit["session"]


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
    self.runner = lambda prompt: HostOutput(text="one two three")
    self.assessor = assessor


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
        _parser().parse_args([])
    with pytest.raises(SystemExit):
        _parser().parse_args(["--prompt", "x"])
    args = _parser().parse_args(["--prompt", "x", "--model", "m"])
    assert args.backend == "fake"