"""Offline propagation checks; no host or model process is launched."""
from types import SimpleNamespace

import pytest

from patristic_ethics import cli, controlled, claude_controlled


@pytest.mark.parametrize("thinking, expected", [("model-default", None), ("on", True), ("off", False)])
def test_assessment_options_reach_interpreter(monkeypatch, thinking, expected):
    seen = {}
    monkeypatch.setattr(cli, "OllamaInterpreter", lambda **kw: seen.update(kw))
    args = cli._parser().parse_args([
        "assess", "--backend", "ollama", "--context-length", "4096", "--thinking", thinking,
    ])
    cli._build_interpreter(args)
    assert seen == dict(model=cli.DEFAULT_MODEL, host=cli.DEFAULT_HOST,
                        timeout_s=cli.DEFAULT_TIMEOUT, num_ctx=4096, think=expected)


def test_controlled_options_reach_shared_interpreter(monkeypatch):
    seen = {}
    monkeypatch.setattr(controlled, "OllamaInterpreter", lambda **kw: seen.update(kw))
    controlled.ControlledClient(backend="ollama", interpreter_context_length=8192,
                                interpreter_think=False)
    assert seen["num_ctx"] == 8192
    assert seen["think"] is False


@pytest.mark.parametrize("module, base", [
    (controlled, ["--model", "host-model"]),
    (claude_controlled, ["--backend", "ollama"]),
])
@pytest.mark.parametrize("explicit", [False, True])
def test_controlled_cli_forwards_only_interpreter_settings(monkeypatch, capsys, module, base, explicit):
    seen = {}
    def client(**kwargs):
        seen.update(kwargs)
        return SimpleNamespace(run=lambda prompt: SimpleNamespace(
            released_text="reviewed", model_invoked=False, action="proceed", failure=None, audit={}))
    monkeypatch.setattr(module, "ControlledClient", client)
    flags = ["--interpreter-context-length", "4096", "--interpreter-thinking", "off", "--revise-once"] if explicit else []
    assert module.main(base + ["--prompt", "hello"] + flags) == 0
    assert seen["allow_revision"] is explicit
    assert seen["interpreter_context_length"] == (4096 if explicit else None)
    assert seen["interpreter_think"] is (False if explicit else None)
    assert capsys.readouterr().out == "reviewed\n"


@pytest.mark.parametrize("module, argv", [
    (cli, ["assess", "--context-length"]),
    (controlled, ["--model", "host-model", "--interpreter-context-length"]),
    (claude_controlled, ["--backend", "ollama", "--interpreter-context-length"]),
])
@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_invalid_context_rejected_before_any_backend(monkeypatch, capsys, module, argv, value):
    with pytest.raises(SystemExit) as exc:
        module.main(argv + [value])
    assert exc.value.code == 2
    assert capsys.readouterr().out == ""
