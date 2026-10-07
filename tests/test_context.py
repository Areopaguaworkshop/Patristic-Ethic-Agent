"""Offline tests for the context envelope contract (plan §5.2)."""

import pytest

from patristic_ethics.context import EnvelopeError, build_envelope, validate_envelope

TRUSTED_BASE = {
    "schema_version": "1",
    "host": {"name": "opencode", "version": "1.18.34", "mode": "native"},
    "session": {"id": "s-1"},
    "turn": {"id": "t-1"},
    "stage": "input",
    "request": "help me sort a list",
    "messages": [
        {"role": "user", "source_id": "m1", "seq": 1, "text": "hello", "origin": "user"},
        {"role": "assistant", "source_id": "m2", "seq": 2, "text": "hi", "origin": "assistant"},
    ],
    "policy_version": "draft",
    "corpus_version": "draft",
}


def test_minimal_envelope_validates_with_defaults():
    env = validate_envelope(TRUSTED_BASE)
    assert env.stage == "input"
    assert env.history.complete is False
    assert env.language == "en"
    assert env.messages[1].seq == 2
    assert env.session.parent_id is None
    assert env.turn.event_id is None
    assert env.policy_version == "draft"


def test_stage_pre_action_requires_proposed_action():
    ok = validate_envelope(
        {
            **TRUSTED_BASE,
            "stage": "pre_action",
            "proposed_action": {"tool": "bash", "arguments": {"command": "ls"}},
        }
    )
    assert ok.proposed_action is not None and ok.proposed_action.tool == "bash"

    with pytest.raises(EnvelopeError) as exc:
        validate_envelope({**TRUSTED_BASE, "stage": "pre_action"})
    assert "proposed_action" in str(exc.value)


def test_stage_output_requires_candidate_response():
    ok = validate_envelope({**TRUSTED_BASE, "stage": "output", "candidate_response": "here you go"})
    assert ok.candidate_response == "here you go"

    with pytest.raises(EnvelopeError) as exc:
        validate_envelope({**TRUSTED_BASE, "stage": "output"})
    assert "candidate_response" in str(exc.value)


def test_proposed_action_rejected_on_input_stage_is_allowed():
    # input stage does not forbid extras; stages only add requirements
    env = validate_envelope(
        {**TRUSTED_BASE, "proposed_action": {"tool": "bash", "arguments": {}}}
    )
    assert env.stage == "input"


def test_duplicate_message_seq_rejected():
    data = {
        **TRUSTED_BASE,
        "messages": [
            {"role": "user", "source_id": "m1", "seq": 1, "text": "a", "origin": "user"},
            {"role": "user", "source_id": "m2", "seq": 1, "text": "b", "origin": "user"},
        ],
    }
    with pytest.raises(EnvelopeError) as exc:
        validate_envelope(data)
    assert "strictly ascending" in str(exc.value)


def test_non_ascending_message_seq_rejected():
    data = {
        **TRUSTED_BASE,
        "messages": [
            {"role": "user", "source_id": "m1", "seq": 2, "text": "a", "origin": "user"},
            {"role": "user", "source_id": "m2", "seq": 1, "text": "b", "origin": "user"},
        ],
    }
    with pytest.raises(EnvelopeError):
        validate_envelope(data)


def test_empty_schema_version_rejected():
    with pytest.raises(EnvelopeError) as exc:
        validate_envelope({**TRUSTED_BASE, "schema_version": "  "})
    assert "schema_version" in str(exc.value)
    assert exc.value.errors


def test_bad_stage_rejected():
    with pytest.raises(EnvelopeError):
        validate_envelope({**TRUSTED_BASE, "stage": "post_hoc"})


def test_bad_message_role_rejected():
    data = {
        **TRUSTED_BASE,
        "messages": [{"role": "developer", "source_id": "m1", "seq": 1, "text": "x", "origin": "user"}],
    }
    with pytest.raises(EnvelopeError):
        validate_envelope(data)


def test_missing_required_field():
    data = {k: v for k, v in TRUSTED_BASE.items() if k != "request"}
    with pytest.raises(EnvelopeError) as exc:
        validate_envelope(data)
    assert "request" in str(exc.value)


def test_envelope_error_is_value_error():
    assert issubclass(EnvelopeError, ValueError)


def test_build_envelope_roundtrip():
    env = build_envelope(
        messages=[{"role": "user", "source_id": "m1", "seq": 5, "text": "q", "origin": "user"}]
    )
    assert env.messages[0].seq == 5
    # model_dump feeds straight back through validate_envelope
    again = validate_envelope(env.model_dump())
    assert again == env


def test_build_envelope_override_stage_with_action():
    env = build_envelope(
        stage="pre_action",
        proposed_action={"tool": "write", "arguments": {"path": "/tmp/x"}},
    )
    assert env.proposed_action is not None and env.proposed_action.arguments == {"path": "/tmp/x"}