"""One native-adapter fixture matrix; synthetic results, not semantic/live proof."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from patristic_ethics.adapters import claude_code, codex
from patristic_ethics.adapters.history import remember
from patristic_ethics.context import validate_envelope

ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "tests/fixtures/host_conformance/scenarios.jsonl"
CASES = [json.loads(line) for line in CASES_PATH.read_text().splitlines()]
PRIOR = "Earlier benign objective in the target session."
INVALID = {"outage", "malformed", "missing-action", "unknown-action", "failed-forward", "conflicting-forward"}


@pytest.mark.parametrize("adapter", [codex, claude_code], ids=["codex", "claude-code"])
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_native_python_shared_matrix(adapter, case, tmp_path, monkeypatch):
    monkeypatch.setenv("PEA_HISTORY_DB", str(tmp_path / "history.db"))
    remember(dict(host=dict(name=adapter.HOST_NAME), session=dict(id="target"),
                  stage="input", request=PRIOR), "proceed")
    captured = []
    def runner(value):
        envelope = json.loads(value) if isinstance(value, str) else value
        captured.append(validate_envelope(envelope))
        if case["fault"] == "outage":
            raise TimeoutError("fixture outage")
        if case["fault"] == "malformed":
            return "malformed"
        return json.dumps(case["result"]) if adapter is claude_code else case["result"]
    payload = dict(session_id=case["session"], turn_id=case["id"], prompt_id=case["id"],
                   hook_event_name="UserPromptSubmit" if case["stage"] == "input" else "PreToolUse",
                   prompt=case["request"], tool_name="test_effect", tool_input={"text":case["request"]})
    protocol = adapter.handle(payload, runner)
    if adapter is claude_code:
        protocol, diagnostic = protocol
    env = captured[0]
    assert env.stage == case["stage"]
    assert env.session.id == case["session"]
    assert [message.text for message in env.messages] == ([PRIOR] if case["session"] == "target" else [])
    assert env.history.complete is False
    if case["stage"] == "pre_action":
        assert env.proposed_action.arguments == {"text":case["request"]}
    action = "withhold" if case["fault"] in INVALID else case["result"]["action"]
    if action in {"refuse", "clarify", "review", "withhold"}:
        if case["stage"] == "input":
            assert protocol["decision"] == "block"
        else:
            assert protocol["hookSpecificOutput"]["permissionDecision"] == "deny"
    elif action == "guide":
        assert protocol["hookSpecificOutput"]["additionalContext"] == "PEA fixture guidance"
    else:
        assert protocol is None


@pytest.mark.skipif(shutil.which("bun") is None or os.environ.get("PEA_RUN_BUN_TEST") != "1",
                    reason="Bun transport requires PEA_RUN_BUN_TEST=1 outside managed sandbox")
def test_opencode_same_native_matrix(tmp_path):
    capture = tmp_path / "captures"
    capture.mkdir()
    cli = tmp_path / "cli.py"
    cli.write_text('''import json, os, pathlib, sys
case = json.loads(pathlib.Path(os.environ["CURRENT_CASE"]).read_text())
pathlib.Path(os.environ["CAPTURES"], case["id"] + ".json").write_text(sys.stdin.read())
if case["fault"] == "outage": sys.exit(7)
print("malformed" if case["fault"] == "malformed" else json.dumps(case["result"]))
''')
    harness = tmp_path / "probe.ts"
    harness.write_text('''import fs from "fs";
import {PeaEthics} from "''' + (ROOT / "adapters/opencode/index.ts").as_posix() + '''";
const cases = fs.readFileSync(process.env.CASES!, "utf8").trim().split("\\n").map(JSON.parse);
const results = [];
for (const c of cases) {
    fs.writeFileSync(process.env.CURRENT_CASE!, JSON.stringify(c));
    const hooks = await PeaEthics({client: {session: {messages: async ({path}) => ({data:
        path.id === "target" ? [{info:{id:"prior",role:"user"},parts:[{text:"''' + PRIOR + '''"}]}] : []
    })}}} as any);
    const output = {parts:[{type:"text",text:c.request}],message:{id:c.id},args:{text:c.request}};
    let blocked = false;
    let effect = false;
    try {
        if (c.stage === "input") await hooks["chat.message"]!({sessionID:c.session,messageID:c.id} as any, output as any);
        else await hooks["tool.execute.before"]!({sessionID:c.session,tool:"test_effect",callID:c.id} as any, output as any);
        if (c.stage === "pre_action") {
            fs.writeFileSync(process.env.CAPTURES! + "/" + c.id + ".effect", "test effect");
            effect = true;
        }
    } catch { blocked = true; }
    results.push({id:c.id,blocked,effect,injected:output.parts.length > 1});
}
console.log(JSON.stringify(results));
''')
    env = {**os.environ, "PEA_ENABLED":"1", "PEA_CLI":f"{sys.executable} {cli}",
           "PEA_WORKDIR":str(ROOT), "PEA_BACKEND":"fake", "CASES":str(CASES_PATH), "CAPTURES":str(capture), "CURRENT_CASE":str(tmp_path / "current.json")}
    env["PEA_LOG"] = str(tmp_path / "adapter.log")
    proc = subprocess.run([shutil.which("bun"), str(harness)], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, proc.stderr
    results = {row["id"]:row for row in json.loads(proc.stdout)}
    for case in CASES:
        assert (capture / (case["id"] + ".json")).exists(), (tmp_path / "adapter.log").read_text()[-1000:]
        env = validate_envelope(json.loads((capture / (case["id"] + ".json")).read_text()))
        assert env.stage == case["stage"]
        assert env.session.id == case["session"]
        assert [message.text for message in env.messages] == ([PRIOR] if case["session"] == "target" else [])
        assert not env.history.complete
        action = "withhold" if case["fault"] in INVALID else case["result"]["action"]
        if case["stage"] == "pre_action":
            assert env.proposed_action.arguments == {"text":case["request"]}
            assert results[case["id"]]["blocked"] is (action in {"refuse","clarify","review","withhold"})
            assert (capture / (case["id"] + ".effect")).exists() is (action in {"proceed", "guide"})
        else:
            assert results[case["id"]]["blocked"] is False  # Native OpenCode input is advisory.
            assert results[case["id"]]["injected"] is (case["fault"] not in INVALID and action in {"guide","refuse","clarify","review"})
