"""Remote interpreter tests against a local HTTP server; no external calls."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from patristic_ethics.context import validate_envelope
from patristic_ethics.interpreter import (
    PROVIDERS,
    InterpreterUnavailable,
    RemoteInterpreter,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "assess" / "benign.json"

OBSERVATION = {
    "requested_assistance": "write a Python function",
    "assistance_type": "benign_discussion",
    "affected_parties": [],
    "topics": ["programming"],
    "expressed_intent": "learn",
    "evidence": [
        {
            "source_id": "current_request",
            "quote": "How do I kill a process on Linux without rebooting?",
        }
    ],
    "benign_explanations": [],
    "unresolved_ambiguity": [],
    "confidence": 0.9,
}


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    requests: list[dict]
    mode: str = "ok"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - match base signature
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        server = self.server
        assert isinstance(server, _Server)
        server.requests.append(
            {"path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body}
        )
        if server.mode == "timeout":
            time.sleep(1.0)
            return
        if server.mode == "schema":
            content = "not json"
            payload = {"choices": [{"message": {"content": content}}]}
        elif self.path.endswith("/messages"):
            payload = {
                "content": [{"type": "text", "text": json.dumps(OBSERVATION)}],
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
        else:
            payload = {
                "choices": [{"message": {"content": json.dumps(OBSERVATION)}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7},
            }
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture()
def server():
    httpd = _Server(("127.0.0.1", 0), _Handler)
    httpd.requests = []
    httpd.mode = "ok"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def _envelope():
    return validate_envelope(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_openai_compatible_request_and_parse(server):
    interpreter = RemoteInterpreter(
        provider="openai",
        model="test-model",
        base_url=f"http://127.0.0.1:{server.server_port}",
        api_key="test-key",
        timeout_s=2.0,
    )
    result = interpreter.interpret(_envelope())
    assert result.requested_assistance == "write a Python function"
    request = server.requests[0]
    assert request["path"] == "/chat/completions"
    assert request["headers"]["authorization"] == "Bearer test-key"
    assert request["body"]["model"] == "test-model"
    assert request["body"]["response_format"] == {"type": "json_object"}
    assert interpreter.last_usage == {"prompt_tokens": 11, "completion_tokens": 7}


def test_anthropic_request_and_parse(server):
    interpreter = RemoteInterpreter(
        provider="anthropic",
        model="test-model",
        base_url=f"http://127.0.0.1:{server.server_port}",
        api_key="test-key",
        timeout_s=2.0,
    )
    result = interpreter.interpret(_envelope())
    assert result.assistance_type == "benign_discussion"
    request = server.requests[0]
    assert request["path"] == "/messages"
    assert request["headers"]["x-api-key"] == "test-key"
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert interpreter.last_usage == {"prompt_tokens": 11, "completion_tokens": 7}


def test_missing_api_key_fails_at_setup(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        RemoteInterpreter(provider="openai", model="test-model", api_key_env=None)


def test_timeout_is_typed(server):
    server.mode = "timeout"
    interpreter = RemoteInterpreter(
        provider="openai",
        model="test-model",
        base_url=f"http://127.0.0.1:{server.server_port}",
        api_key="test-key",
        timeout_s=0.1,
    )
    with pytest.raises(InterpreterUnavailable) as caught:
        interpreter.interpret(_envelope())
    assert caught.value.failure.kind == "timeout"


def test_schema_failure_is_typed(server):
    server.mode = "schema"
    interpreter = RemoteInterpreter(
        provider="openai",
        model="test-model",
        base_url=f"http://127.0.0.1:{server.server_port}",
        api_key="test-key",
        timeout_s=2.0,
    )
    with pytest.raises(InterpreterUnavailable) as caught:
        interpreter.interpret(_envelope())
    assert caught.value.failure.kind == "schema"


def test_provider_presets_keep_local_ollama_separate():
    assert PROVIDERS["deepseek"]["base_url"] == "https://api.deepseek.com"
    assert PROVIDERS["deepseek"]["api_key_env"] == "DEEPSEEK_API_KEY"
    assert PROVIDERS["anthropic"]["api_key_env"] == "ANTHROPIC_API_KEY"
    assert "ollama" not in PROVIDERS
