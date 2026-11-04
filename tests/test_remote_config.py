"""Environment wiring for the MCP server and native adapters."""

from __future__ import annotations

import subprocess

import pytest

from patristic_ethics import mcp_server
from patristic_ethics.adapters import claude_code, codex
from patristic_ethics.interpreter import FakeInterpreter, OllamaInterpreter, RemoteInterpreter


def _remote_env(monkeypatch):
    monkeypatch.setenv("PEA_BACKEND", "remote")
    monkeypatch.setenv("PEA_PROVIDER", "openai")
    monkeypatch.setenv("PEA_MODEL", "test-model")
    monkeypatch.setenv("PEA_INTERPRETER_MODEL", "test-model")
    monkeypatch.setenv("PEA_REMOTE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("PEA_API_KEY_ENV", "TEST_REMOTE_KEY")
    monkeypatch.setenv("TEST_REMOTE_KEY", "dummy")
    monkeypatch.setenv("PEA_INTERPRETER_TIMEOUT", "8")
    monkeypatch.setenv("PEA_JSON_MODE", "1")


def test_mcp_factory_builds_remote_from_env(monkeypatch):
    _remote_env(monkeypatch)
    interpreter = mcp_server._default_interpreter_factory()
    assert isinstance(interpreter, RemoteInterpreter)
    assert interpreter.provider == "openai"
    assert interpreter.model == "test-model"
    assert interpreter.base_url == "https://example.invalid/v1"
    assert interpreter.timeout_s == 8.0


def test_mcp_factory_keeps_fake_and_ollama(monkeypatch):
    monkeypatch.setenv("PEA_BACKEND", "fake")
    assert isinstance(mcp_server._default_interpreter_factory(), FakeInterpreter)

    monkeypatch.setenv("PEA_BACKEND", "ollama")
    monkeypatch.setenv("PEA_MODEL", "test-ollama")
    monkeypatch.setenv("PEA_HOST", "http://localhost:11434")
    interpreter = mcp_server._default_interpreter_factory()
    assert isinstance(interpreter, OllamaInterpreter)
    assert interpreter.model == "test-ollama"


def test_codex_runner_passes_remote_flags(monkeypatch):
    _remote_env(monkeypatch)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, '{"action":"proceed"}\n', "")

    monkeypatch.setattr(codex.subprocess, "run", fake_run)
    assert codex._run_cli({"request": "x"}) == {"action": "proceed"}
    cmd = captured["cmd"]
    assert cmd[cmd.index("--backend") + 1] == "remote"
    assert cmd[cmd.index("--provider") + 1] == "openai"
    assert cmd[cmd.index("--model") + 1] == "test-model"
    assert cmd[cmd.index("--remote-url") + 1] == "https://example.invalid/v1"
    assert cmd[cmd.index("--api-key-env") + 1] == "TEST_REMOTE_KEY"
    assert cmd[cmd.index("--timeout") + 1] == "8"


def test_claude_runner_passes_remote_flags(monkeypatch):
    _remote_env(monkeypatch)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, '{"action":"proceed"}\n', "")

    monkeypatch.setattr(claude_code.subprocess, "run", fake_run)
    assert claude_code.default_runner('{"request":"x"}') == '{"action":"proceed"}\n'
    cmd = captured["cmd"]
    assert cmd[cmd.index("--backend") + 1] == "remote"
    assert cmd[cmd.index("--provider") + 1] == "openai"
    assert cmd[cmd.index("--model") + 1] == "test-model"
    assert cmd[cmd.index("--remote-url") + 1] == "https://example.invalid/v1"
    assert cmd[cmd.index("--api-key-env") + 1] == "TEST_REMOTE_KEY"
    assert cmd[cmd.index("--timeout") + 1] == "8"


def test_remote_missing_model_fails_closed(monkeypatch):
    _remote_env(monkeypatch)
    monkeypatch.delenv("PEA_MODEL")
    with pytest.raises(ValueError, match="requires an explicit model"):
        mcp_server._default_interpreter_factory()
