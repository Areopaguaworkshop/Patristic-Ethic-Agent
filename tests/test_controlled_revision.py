"""One optional revision, full rechecking, and quarantined host history."""
import json

import pytest

from patristic_ethics.assess import AssessResult
from patristic_ethics.controlled import ControlledClient, HostOutput, WITHHELD_MESSAGE
from patristic_ethics.guidance import GuidanceResult
from patristic_ethics.interpreter import InterpreterFailure

BAD = 'Augustine said "the moon is made of cheese".'
SAFE = "Here is a safe answer without invented quotations."


def make_client(revision=SAFE, *, enabled=True, second_action="proceed", second_failure=False, callback=None):
    calls, assessed = [], []
    def runner(prompt, session_id=None):
        calls.append((prompt, session_id))
        text = BAD if len(calls) == 1 else revision
        return HostOutput(text=text, session_id="candidate-session")
    def assessor(envelope):
        if envelope.stage == "input":
            return AssessResult(action="proceed")
        assessed.append(envelope.candidate_response)
        if second_failure and len(assessed) == 2:
            raise RuntimeError("UNREVIEWED_EXCEPTION_MARKER")
        return AssessResult(action="proceed" if len(assessed) == 1 else second_action,
                            guidance=GuidanceResult(text="Reviewed PEA alternative"))
    client = ControlledClient(runner=runner, assessor=assessor, allow_revision=enabled, revise_fn=callback)
    return client, calls, assessed


def test_fresh_revision_rechecked_and_released_without_original_session_reuse():
    client, calls, assessed = make_client()
    result = client.run("What did Augustine teach?")
    assert len(calls) == 2
    assert calls[1][1] is None
    assert json.loads(calls[1][0].split("\n", 1)[1])["candidate_for_revision"] == BAD
    assert assessed == [BAD, SAFE]
    assert result.released_text == SAFE
    assert result.buffered == BAD  # Original remains only in the in-memory result.
    assert result.action == "proceed"
    assert result.audit["revision_attempted"] is True
    assert result.audit["revised_candidate_checked"] is True
    assert client._host_session_id is None
    assert all(message["text"] != BAD for message in client._visible_history)
    client.run("next")
    assert calls[-1][1] is None
    assert json.dumps(BAD) not in calls[-1][0]


@pytest.mark.parametrize("text, action, failure", [
    (BAD, "proceed", False),
    (SAFE, "refuse", False),
    (SAFE, "proceed", True),
])
def test_failed_recheck_never_retries_again_or_releases_revision(text, action, failure):
    client, calls, assessed = make_client(text, second_action=action, second_failure=failure)
    result = client.run("question")
    assert len(calls) == 2
    assert assessed == [BAD, text]
    assert result.action != "proceed"
    assert result.released_text in {WITHHELD_MESSAGE, "Reviewed PEA alternative"}
    assert client._host_session_id is None
    if failure:
        assert "UNREVIEWED_EXCEPTION_MARKER" not in str(result.failure)


@pytest.mark.parametrize("value", [None, "", 123, "raise"])
def test_revision_callback_failure_falls_back_without_rechecking_invalid_data(value):
    attempts = []
    def callback(candidate, problems):
        attempts.append((candidate, problems))
        if value == "raise":
            raise RuntimeError("UNREVIEWED_EXCEPTION_MARKER")
        return value
    client, calls, assessed = make_client(callback=callback)
    result = client.run("question")
    assert len(attempts) == 1
    assert len(calls) == 1
    assert assessed == [BAD]
    assert result.released_text == WITHHELD_MESSAGE
    assert result.audit["revision_attempted"] is True
    assert result.audit["revised_candidate_checked"] is False
    assert "UNREVIEWED_EXCEPTION_MARKER" not in str(result.failure)


def test_revision_is_disabled_by_default_and_good_outputs_never_revise():
    client, calls, assessed = make_client(enabled=False)
    assert client.run("question").released_text == WITHHELD_MESSAGE
    assert len(calls) == 1
    client = ControlledClient(allow_revision=True, assessor=lambda env: AssessResult(action="proceed"),
                              runner=lambda prompt, session_id=None: HostOutput(text=SAFE),
                              revise_fn=lambda *args: pytest.fail("already valid output must not revise"))
    assert client.run("question").released_text == SAFE


@pytest.mark.parametrize("stage", ["input", "output"])
def test_evaluator_failure_never_invokes_revision(stage):
    calls = []
    def assessor(env):
        if env.stage == stage:
            return AssessResult(action="withhold", failure=InterpreterFailure(reason="unavailable"))
        return AssessResult(action="proceed")
    def runner(prompt, session_id=None):
        calls.append(prompt)
        return HostOutput(text=BAD)
    client = ControlledClient(allow_revision=True, assessor=assessor, runner=runner,
                              revise_fn=lambda *args: pytest.fail("evaluator outage must not revise"))
    result = client.run("question")
    assert result.released_text == WITHHELD_MESSAGE
    assert len(calls) == (1 if stage == "output" else 0)


def test_semantic_replacement_also_can_request_one_checked_revision():
    seen = []
    def assessor(env):
        if env.stage == "input":
            return AssessResult(action="proceed")
        seen.append(env.candidate_response)
        return AssessResult(action="refuse" if len(seen) == 1 else "proceed",
                            guidance=GuidanceResult(text="Reviewed alternative"))
    client = ControlledClient(allow_revision=True, assessor=assessor,
                              runner=lambda prompt, session_id=None: HostOutput(text="bad answer"),
                              revise_fn=lambda candidate, problems: SAFE)
    assert client.run("question").released_text == SAFE
    assert seen == ["bad answer", SAFE]


def test_revision_cannot_release_when_proceed_conflicts_with_semantic_refusal():
    from types import SimpleNamespace
    seen = []
    def assessor(env):
        if env.stage == "input":
            return AssessResult(action="proceed")
        seen.append(env.candidate_response)
        if len(seen) == 1:
            return AssessResult(action="proceed")
        return AssessResult(action="proceed", decision=SimpleNamespace(disposition="refuse"))
    client = ControlledClient(allow_revision=True, assessor=assessor,
                              runner=lambda prompt, session_id=None: HostOutput(text=BAD),
                              revise_fn=lambda candidate, problems: SAFE)
    result = client.run("question")
    assert seen == [BAD, SAFE]
    assert result.released_text == WITHHELD_MESSAGE
    assert result.failure == "assessment failed: ValueError"
