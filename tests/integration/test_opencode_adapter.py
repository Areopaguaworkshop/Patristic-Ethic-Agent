"""M4a offline tests + live-gated plugin probe for the OpenCode adapter.

Offline checks (always run): the adapter plugin source exists, wires the
three host hooks, carries the recursion guard, never writes to stdout, and
injects a full TextPart; the example config parses with tools gated.

Live-gated (PEA_LIVE_PLUGIN_PROBE=1 + opencode on PATH): runs
scripts/probe_pea_plugin.sh and requires S1 evidence to contain "PEA:".
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "adapters" / "opencode" / "index.ts"
EXAMPLE_CONFIG = ROOT / "examples" / "opencode" / "opencode.json"
PROBE = ROOT / "scripts" / "probe_pea_plugin.sh"


def test_adapter_files_exist() -> None:
    assert ADAPTER.is_file(), "adapters/opencode/index.ts missing"
    assert (ROOT / "adapters" / "opencode" / "package.json").is_file()


def test_adapter_wires_host_hooks() -> None:
    src = ADAPTER.read_text(encoding="utf-8")
    for hook in ("chat.message", "tool.execute.before", "tool.execute.after"):
        assert f'"{hook}"' in src, f"adapter missing hook: {hook}"
    # Named export per host contract.
    assert "export const PeaEthics" in src
    assert 'from "@opencode-ai/plugin"' in src


def test_adapter_does_not_exempt_agent_supplied_tool_arguments() -> None:
    src = ADAPTER.read_text(encoding="utf-8")
    assert "recursion_guard" not in src
    assert "argsJson.includes" not in src
    assert "buildPreActionEnvelope(sessionID, input?.callID ?? \"\", tool, output?.args, client)" in src
    assert '"assessment unavailable; tool call withheld"' in src
    assert '"assessment failed; tool call withheld"' in src
    assert 'new Set(["refuse", "clarify", "review", "withhold"])' in src


def test_adapter_never_writes_stdout() -> None:
    src = ADAPTER.read_text(encoding="utf-8")
    assert "console.log(" not in src, "adapter must never write to stdout"


def test_adapter_injects_full_textpart() -> None:
    src = ADAPTER.read_text(encoding="utf-8")
    # Full TextPart shape: id, sessionID, messageID, type "text", text —
    # the host zod schema rejects anything less (M0 probe S3 evidence).
    for field in ("id:", "sessionID:", "messageID:", 'type: "text"', "text:"):
        assert field in src, f"TextPart field missing from injection: {field}"
    # input.messageID may be absent in run mode -> fall back to output.message.id.
    assert "input?.messageID ?? output?.message?.id" in src
    assert "PEA: " in src


def test_example_config_parses_and_gates_tools() -> None:
    cfg = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    tools = cfg.get("tools")
    assert isinstance(tools, dict) and tools.get("*") is False, (
        "example config must disable wildcard tools"
    )
    models = cfg["provider"]["ollama"]["models"]
    assert "deepseek-v4.1-flash:cloud" in models
    assert "ornith-1.5:9b" in models


@pytest.mark.skipif(
    os.environ.get("PEA_LIVE_PLUGIN_PROBE") != "1" or shutil.which("opencode") is None,
    reason="live plugin probe requires PEA_LIVE_PLUGIN_PROBE=1 and opencode on PATH",
)
def test_live_plugin_probe() -> None:
    result = subprocess.run(
        ["sh", str(PROBE)],
        capture_output=True,
        text=True,
        timeout=1500,
    )
    stdout = result.stdout
    # Script may exit 0 with SKIP (no model) — a skip is acceptable only
    # with an explicit message, never silence.
    if stdout.startswith("SKIP"):
        pytest.skip(stdout.splitlines()[0])
    # S1 evidence must be real: an injected "PEA: " audit entry.
    assert "S1" in stdout, f"probe produced no S1 line:\n{stdout}\n{result.stderr}"
    assert 'injected":"PEA: ' in stdout or '"injected":"PEA: ' in Path(
        "/tmp/pea-plugin-probe/out/pea_audit.jsonl"
    ).read_text(encoding="utf-8"), "S1 evidence must contain an injected PEA: entry"
    assert "S1 harmful" in stdout and "FAIL" not in stdout.split("S1 harmful")[1].splitlines()[0]
    assert "S2 benign" in stdout and "FAIL" not in stdout.split("S2 benign")[1].splitlines()[0]
    # S3 may be INCONCLUSIVE (documented: fake backend has no generic
    # tool-call marker) but must not silently pass without evidence.
    s3_line = stdout.split("S3 tool gate (benign payload):")[1].splitlines()[0]
    assert "PASS" in s3_line or "INCONCLUSIVE" in s3_line, f"S3 unreported: {s3_line}"
    # S3b (disallowed-effect criterion) must PASS or report INCONCLUSIVE
    # with a reason — never silently absent.
    s3b_line = stdout.split("S3b tool gate (harmful payload, disallowed effect):")[1].splitlines()[0]
    assert "PASS" in s3b_line or "INCONCLUSIVE" in s3b_line, f"S3b unreported: {s3b_line}"
    if "PASS" in s3b_line:
        # Blocked call: no after-hook entry for the blocked callID.
        audit = Path("/tmp/pea-plugin-probe/out/pea_audit.jsonl").read_text(encoding="utf-8")
        blocked_callids = []
        for line in audit.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("blocked") is True:
                blocked_callids.append(obj.get("callID"))
        assert any(cid for cid in blocked_callids) or blocked_callids == [None], (
            "blocked verdict present but no callID recorded"
        )
        for cid in [c for c in blocked_callids if c]:
            after = [l for l in audit.splitlines() if '"tool.execute.after"' in l and cid in l]
            assert not after, f"after-hook fired for blocked call {cid}"
    # S4 (multi-turn) and S5 (controlled) must be reported with verdicts.
    s4_line = stdout.split("S4 multi-turn harmful continuation:")[1].splitlines()[0]
    assert "PASS" in s4_line or "INCONCLUSIVE" in s4_line, f"S4 unreported: {s4_line}"
    s5_line = stdout.split("S5 controlled client (blocked content never displayed):")[1].splitlines()[0]
    assert "PASS" in s5_line or "INCONCLUSIVE" in s5_line or "FAIL" in s5_line, (
        f"S5 unreported: {s5_line}"
    )
    if "PASS" in s5_line:
        assert '"model_invoked": false' in Path(
            "/tmp/pea-controlled-probe/out/stderr.log"
        ).read_text(encoding="utf-8") or '"model_invoked":false' in Path(
            "/tmp/pea-controlled-probe/out/stderr.log"
        ).read_text(encoding="utf-8")


@pytest.mark.skipif(
    os.environ.get("PEA_LIVE_PLUGIN_PROBE") != "1",
    reason="evidence-excerpt checks require a completed live run (PEA_LIVE_PLUGIN_PROBE=1)",
)
def test_m4_evidence_files_record_acceptance() -> None:
    """M4c: evidence excerpts must exist and carry the acceptance markers.

    The files are written by hand from the live run's raw logs (never
    generated by the probe script), so after a live run they must contain
    the recorded verdicts and the decisive evidence lines.
    """
    ev = ROOT / "tests" / "fixtures" / "opencode_probe" / "evidence"
    s4 = (ev / "S4_multiturn.txt").read_text(encoding="utf-8")
    assert "ses_eec56fa29ffekFsmmt7xkmsvRC" in s4, "S4 must cite the continued sessionID"
    assert '"action":"refuse","injected":"PEA: ' in s4
    assert "PASS" in s4
    assert '"action":"proceed"' in s4, "S4 must record the benign turn-1 allow"

    s5 = (ev / "S5_controlled.txt").read_text(encoding="utf-8")
    assert '"model_invoked": false' in s5
    assert '"buffered_chars": 0' in s5
    assert "outside what I can help with" in s5
    assert "PASS" in s5

    s3b = (ev / "S3b_tool_effect.txt").read_text(encoding="utf-8")
    assert '"blocked":true' in s3b
    assert '"error":"PEA: refuse' in s3b
    assert "PASS" in s3b

    result_md = (ev / "RESULT.md").read_text(encoding="utf-8")
    assert "M4 acceptance evidence" in result_md
    for marker in ("S4_multiturn.txt", "S5_controlled.txt", "S3b_tool_effect.txt"):
        assert marker in result_md
    # All five acceptance rows must be recorded with a verdict.
    for num in ("| 1 |", "| 2 |", "| 3 |", "| 4 |", "| 5 |"):
        assert num in result_md, f"RESULT.md missing acceptance row {num}"
