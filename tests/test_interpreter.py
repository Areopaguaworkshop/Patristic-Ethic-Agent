"""Offline tests for the structured interpreter contract and backends.

All ollama interaction is monkeypatched; the live test is env-gated
(PEA_OLLAMA_LIVE=1) and additionally skips when a 2-second TCP probe
to the ollama host fails.
"""

import json
import os
import socket
from unittest.mock import MagicMock

import pytest

from patristic_ethics.context import build_envelope
from patristic_ethics.interpreter import (
    Evidence,
    FakeInterpreter,
    InterpreterFailure,
    InterpreterUnavailable,
    Observation,
    OllamaInterpreter,
)

OBS = Observation(
    requested_assistance="write a poem",
    affected_parties=["self"],
    topics=["poetry"],
    expressed_intent="creative writing",
    evidence=[Evidence(source_id="m1", quote="write me a poem")],
    benign_explanations=["ordinary creative request"],
    unresolved_ambiguity=[],
    confidence=0.9,
)


def obs_dict():
    return OBS.model_dump()


# --- FakeInterpreter -------------------------------------------------------


def test_fake_interpreter_substring_match():
    fake = FakeInterpreter({"poem": OBS})
    env = build_envelope(request="please write me a poem about spring")
    assert fake.interpret(env) == OBS
    assert fake.calls == 1


def test_fake_interpreter_first_match_wins():
    other = OBS.model_copy(update={"requested_assistance": "other"})
    fake = FakeInterpreter([("spring", other), ("poem", OBS)])
    env = build_envelope(request="write a poem about spring")
    assert fake.interpret(env).requested_assistance == "other"


def test_fake_interpreter_no_match_returns_benign_default():
    fake = FakeInterpreter({"poem": OBS})
    env = build_envelope(request="refactor my function")
    result = fake.interpret(env)
    assert result.requested_assistance == "ordinary work"
    assert result.benign_explanations
    assert fake.calls == 1


def test_fake_interpreter_counts_calls():
    fake = FakeInterpreter({"poem": OBS})
    env = build_envelope(request="poem")
    fake.interpret(env)
    fake.interpret(env)
    fake.interpret(env)
    assert fake.calls == 3


def test_fake_interpreter_returns_copies():
    fake = FakeInterpreter({"poem": OBS})
    env = build_envelope(request="poem")
    a = fake.interpret(env)
    b = fake.interpret(env)
    a.requested_assistance = "mutated"
    assert fake.interpret(env).requested_assistance == "write a poem"
    assert b.requested_assistance == "write a poem"


# --- OllamaInterpreter failure typing (monkeypatched client) ---------------


def make_offline_ollama(monkeypatch):
    interp = OllamaInterpreter(model="test-model", host="http://localhost:11434")
    client = MagicMock()
    interp._client = client
    return interp, client


def test_ollama_connection_error(monkeypatch):
    interp, client = make_offline_ollama(monkeypatch)
    client.chat.side_effect = ConnectionError("refused")
    with pytest.raises(InterpreterUnavailable) as exc:
        interp.interpret(build_envelope(request="anything"))
    assert exc.value.failure.kind == "connection"


def test_ollama_response_error(monkeypatch):
    from ollama import ResponseError

    interp, client = make_offline_ollama(monkeypatch)
    client.chat.side_effect = ResponseError("model not found", status_code=404)
    with pytest.raises(InterpreterUnavailable) as exc:
        interp.interpret(build_envelope(request="anything"))
    assert exc.value.failure.kind == "other"
    assert "404" in (exc.value.failure.detail or "")


def test_ollama_timeout(monkeypatch):
    import httpx

    interp, client = make_offline_ollama(monkeypatch)
    client.chat.side_effect = httpx.ReadTimeout("read timed out")
    with pytest.raises(InterpreterUnavailable) as exc:
        interp.interpret(build_envelope(request="anything"))
    assert exc.value.failure.kind == "timeout"


def test_ollama_invalid_json_is_schema_failure(monkeypatch):
    interp, client = make_offline_ollama(monkeypatch)
    resp = MagicMock()
    resp.message.content = "not json at all"
    client.chat.return_value = resp
    with pytest.raises(InterpreterUnavailable) as exc:
        interp.interpret(build_envelope(request="anything"))
    assert exc.value.failure.kind == "schema"


def test_ollama_schema_mismatch_is_schema_failure(monkeypatch):
    interp, client = make_offline_ollama(monkeypatch)
    resp = MagicMock()
    # valid JSON, wrong shape: missing required fields
    resp.message.content = json.dumps({"unrelated": "payload"})
    client.chat.return_value = resp
    with pytest.raises(InterpreterUnavailable) as exc:
        interp.interpret(build_envelope(request="anything"))
    assert exc.value.failure.kind == "schema"


def test_ollama_success_parses_observation(monkeypatch):
    interp, client = make_offline_ollama(monkeypatch)
    resp = MagicMock()
    resp.message.content = json.dumps(obs_dict())
    client.chat.return_value = resp
    result = interp.interpret(build_envelope(request="write a poem"))
    assert result == OBS
    # one attempt only: exactly one call, no retries even on failure paths
    assert client.chat.call_count == 1


def test_ollama_no_retry_on_failure(monkeypatch):
    interp, client = make_offline_ollama(monkeypatch)
    client.chat.side_effect = ConnectionError("refused")
    with pytest.raises(InterpreterUnavailable):
        interp.interpret(build_envelope(request="anything"))
    assert client.chat.call_count == 1


def test_ollama_sends_schema_and_zero_temperature(monkeypatch):
    interp, client = make_offline_ollama(monkeypatch)
    resp = MagicMock()
    resp.message.content = json.dumps(obs_dict())
    client.chat.return_value = resp
    interp.interpret(build_envelope(request="x"))
    kwargs = client.chat.call_args.kwargs
    schema = kwargs["format"]
    assert schema["$defs"]["Evidence"]["properties"] == {
        "source_id": {"title": "Source Id", "type": "string"},
        "quote": {"title": "Quote", "type": "string"},
    }
    assert all(schema["properties"][k]["maxItems"] == 10 for k in ("evidence", "topics"))
    assert kwargs["options"] == {"temperature": 0, "num_predict": 512}
    assert kwargs["model"] == "test-model"
    assert "tools" not in kwargs or not kwargs["tools"]


def test_interpreter_failure_dataclass():
    f = InterpreterFailure(reason="r", detail="d", kind="timeout")
    assert (f.reason, f.detail, f.kind) == ("r", "d", "timeout")


def test_observation_schema_roundtrip():
    parsed = Observation.model_validate(obs_dict())
    assert parsed.confidence == 0.9
    assert parsed.evidence[0].source_id == "m1"


def test_observation_confidence_bounds():
    with pytest.raises(Exception):
        Observation.model_validate({**obs_dict(), "confidence": 1.5})
    with pytest.raises(Exception):
        Observation.model_validate({**obs_dict(), "confidence": -0.1})
    assert Observation.model_validate({**obs_dict(), "confidence": None}).confidence is None


# --- Live ollama test (env-gated) ------------------------------------------


def _tcp_probe(host: str, port: int, timeout_s: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


@pytest.mark.skipif(os.environ.get("PEA_OLLAMA_LIVE") != "1", reason="PEA_OLLAMA_LIVE not set")
def test_live_ollama_interpret():
    host_url = os.environ.get("PEA_OLLAMA_HOST", "http://localhost:11434")
    from urllib.parse import urlparse

    parsed = urlparse(host_url)
    hostname = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not _tcp_probe(hostname, port):
        pytest.skip(f"no ollama listening at {host_url}")

    model = os.environ.get("PEA_OLLAMA_MODEL", "ornith-1.5:9b")
    timeout_s = float(os.environ.get("PEA_OLLAMA_TIMEOUT", "600"))
    interp = OllamaInterpreter(model=model, host=host_url, timeout_s=timeout_s)
    env = build_envelope(
        request="What is the capital of France?",
        messages=[],
    )
    observation = interp.interpret(env)
    assert isinstance(observation, Observation)
    assert observation.requested_assistance