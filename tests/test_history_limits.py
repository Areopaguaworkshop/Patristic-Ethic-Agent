"""Bounded history and honest loss/provenance metadata; no model inference."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from patristic_ethics.assess import AssessResult, _validate_observation_evidence
from patristic_ethics.context import build_envelope
from patristic_ethics.controlled import ControlledClient, HostOutput
from patristic_ethics.interpreter import Evidence, Observation, OllamaInterpreter

ROOT = Path(__file__).resolve().parents[1]


def test_controlled_window_keeps_unique_sources_reports_loss_and_resets_session():
    seen = []
    calls = []
    def assessor(envelope):
        seen.append(envelope)
        return AssessResult(action="proceed")
    def runner(prompt, session_id=None):
        calls.append((prompt, session_id))
        return HostOutput(text="answer", session_id="host-session")
    client = ControlledClient(assessor=assessor, runner=runner)
    for index in range(23):
        client.run(f"turn {index}")
    env = seen[-2]
    assert len(env.messages) == 40
    assert env.history.complete is False
    assert "seq 1–4" in env.history.omitted_ranges[0]
    ids = [message.source_id for message in env.messages]
    assert len(set(ids)) == 40
    assert env.messages[0].seq == 5
    assert calls[-1][1] is None
    assert json.loads(calls[-1][0])["history"]["complete"] is False
    client.run("new session", session_id="other")
    assert seen[-2].messages == []
    assert seen[-2].history.complete is True
    assert calls[-1] == ("new session", None)


def test_overlong_history_not_sliced_into_false_verbatim_evidence():
    client = ControlledClient(assessor=lambda envelope: AssessResult(action="proceed"),
                              runner=lambda prompt, session_id=None: HostOutput(text="x" * 16001))
    client.run("original antecedent")
    env = client._envelope(stage="input", prompt="do that", session_id="s", candidate=None)
    assert env.messages == []
    assert not env.history.complete
    assert env.history.omitted_ranges
    payload = json.loads(client._host_prompt("do that"))
    assert payload["history"]["omitted_ranges"]


def test_interpreter_sees_history_loss_and_summary_provenance():
    env = build_envelope(request="do that", history={"complete": False,
        "omitted_ranges": ["messages 1–10 omitted"], "collection_errors": ["compaction"]},
        summary={"source_id": "summary-1", "text": "Earlier objective unknown", "refs": ["m1"]})
    interpreter = OllamaInterpreter.__new__(OllamaInterpreter)
    prompt = interpreter._prompt(env)
    assert '"complete": false' in prompt
    assert "messages 1–10 omitted" in prompt and "compaction" in prompt
    assert 'Summary summary-1 (refs=["m1"]): Earlier objective unknown' in prompt
    assert "never invent it" in prompt
    observation = Observation(requested_assistance="unknown", expressed_intent="unknown",
        evidence=[Evidence(source_id="summary-1", quote="Earlier objective unknown")])
    _validate_observation_evidence(observation, env)
    legacy = build_envelope(summary={"text": "summary text", "refs": []})
    assert legacy.summary.source_id == "summary"


@pytest.mark.skipif(shutil.which("bun") is None or os.environ.get("PEA_RUN_BUN_TEST") != "1",
                    reason="Bun pipe checks require PEA_RUN_BUN_TEST=1 outside the managed sandbox")
@pytest.mark.parametrize("kind", ["bounded", "nontext", "overlong"])
def test_opencode_real_plugin_collects_bounded_incomplete_text_snapshot(tmp_path, kind):
    if kind == "bounded":
        rows = [dict(info=dict(id=f"m{i}", role="user"), parts=[dict(text=f"message {i}")]) for i in range(50)]
    elif kind == "nontext":
        rows = [dict(info=dict(id="image", role="user"), parts=[dict(type="file")])]
    else:
        rows = [dict(info=dict(id="long", role="user"), parts=[dict(text="x" * 16001)])]
    capture = tmp_path / "envelope.json"
    fixture = tmp_path / "rows.json"
    fixture.write_text(json.dumps(rows))
    cli = tmp_path / "cli.py"
    cli.write_text('import sys, os, pathlib\npathlib.Path(os.environ["CAPTURE"]).write_text(sys.stdin.read())\nprint(\'{"action":"proceed"}\')\n')
    harness = tmp_path / "probe.ts"
    harness.write_text('''import fs from "fs";
import {PeaEthics} from "''' + (ROOT / "adapters/opencode/index.ts").as_posix() + '''";
const rows = JSON.parse(fs.readFileSync(process.env.ROWS!, "utf8"));
const hooks = await PeaEthics({client: {session: {messages: async () => ({data: rows})}}} as any);
await hooks["chat.message"]!({sessionID: "session", messageID: "current"} as any,
    {parts: [{type: "text", text: "do that"}], message: {id: "current"}} as any);
''')
    env = {**os.environ, "PEA_ENABLED": "1", "PEA_CLI": f"{sys.executable} {cli}",
           "PEA_WORKDIR": str(ROOT), "PEA_BACKEND": "fake", "ROWS": str(fixture), "CAPTURE": str(capture)}
    env.pop("PEA_LOG", None)
    proc = subprocess.run([shutil.which("bun"), str(harness)], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    envelope = json.loads(capture.read_text())
    assert envelope["history"]["complete"] is False
    assert envelope["history"]["collection_errors"]
    if kind == "bounded":
        assert len(envelope["messages"]) == 40
        assert envelope["messages"][0]["source_id"] == "m10"
        assert envelope["messages"][0]["seq"] == 11
        assert envelope["history"]["omitted_ranges"]
    else:
        assert envelope["messages"] == []
        assert envelope["history"]["collection_errors"] if kind == "nontext" else envelope["history"]["omitted_ranges"]


def test_reported_missing_antecedent_clarifies_without_host_invocation():
    from patristic_ethics.assess import assess
    from patristic_ethics.interpreter import FakeInterpreter
    from patristic_ethics.policy import load_policy
    observed = []
    observation = Observation(requested_assistance="do that", expressed_intent="unknown",
        evidence=[Evidence(source_id="current_request", quote="do that")],
        unresolved_ambiguity=["the earlier antecedent was omitted"], confidence=0.2)
    def assessor(envelope):
        observed.append(envelope)
        return assess(envelope, interpreter=FakeInterpreter([("do that", observation)]),
                      policy_doc=load_policy(ROOT / "policy/rules.json"), db_path=None)
    def unexpected_host(*args, **kwargs):
        pytest.fail("ambiguous missing antecedent must not invoke the host")
    client = ControlledClient(assessor=assessor, runner=unexpected_host)
    client._remember("earlier objective", "x" * 16001)
    result = client.run("do that")
    assert not observed[0].history.complete
    assert observed[0].history.omitted_ranges
    assert result.action == "clarify"
    assert result.model_invoked is False
