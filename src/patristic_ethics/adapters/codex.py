"""PEA native Codex adapter (Codex CLI 0.160.0 hooks).

Runs as a Codex hook command: reads ONE hook JSON payload from stdin,
maps it to a ContextEnvelope, spawns the frozen PEA CLI
(``python -m patristic_ethics.cli assess --stdin``, 15 s timeout) and
prints ONE Codex hook-protocol JSON line to stdout (exit 0). Diagnostics
go to stderr only — stdout carries protocol output or nothing.

Documented limits of native Codex mode:

- FAIL-OPEN: a callback error, timeout or malformed response does NOT
  block the tool or prompt. This hook exits 0 with empty stdout on every
  failure path (Codex documents fail-open hook behavior; its default hook
  timeout is 600 s, the PEA CLI subprocess here is capped at 15 s).
- The transcript is NOT parsed: ``transcript_path`` is documented as NOT
  stable, so ``messages`` stays empty and ``history.complete`` is always
  false on Codex.
- Enforcement is best-effort: there is no MessageDisplay event on Codex
  (no before-display guarantee) and hooks fail open, so strict guarantees
  require controlled mode / an agent sandbox, not this adapter alone.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from ..context import EnvelopeError, validate_envelope

HOST_NAME = "codex"
HOST_VERSION_DEFAULT = "0.160.0"
POLICY_VERSION = "0.1.0-draft"
CORPUS_VERSION = "0.1.0-draft"
CLI_TIMEOUT_S = 15.0
REASON_MAX = 500

# Actions that stop a prompt/tool at the host protocol level.
_BLOCKING_ACTIONS = {"refuse", "clarify", "review", "withhold"}


def _guidance_text(assess_result: dict) -> str:
    guidance = assess_result.get("guidance")
    if isinstance(guidance, dict) and isinstance(guidance.get("text"), str):
        return guidance["text"]
    return ""


def _tool_arguments(payload: dict) -> dict:
    for key in ("tool_input", "arguments", "input"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def build_envelope(payload: dict) -> dict | None:
    """Codex hook payload -> ContextEnvelope dict; None on any mismatch.

    Deliberate mapping choices (documented):
    - ``messages`` is always empty and ``history.complete`` is always
      false: the Codex transcript format is unstable and is never parsed.
    - Unmapped events (SessionStart, PermissionRequest, anything else)
      return None -> fail-open, no assessment, no output.
    """
    event = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    if session_id is None:
        return None
    turn_id = payload.get("turn_id") or f"turn-{session_id}"
    version = (
        payload.get("codex_version") or payload.get("version") or HOST_VERSION_DEFAULT
    )

    envelope: dict = {
        "schema_version": "1",
        "host": {"name": HOST_NAME, "version": version, "mode": "native"},
        "session": {"id": session_id},
        "turn": {"id": turn_id, "event_id": turn_id},
        "messages": [],  # transcript_path is NOT parsed (format unstable)
        "earlier_excerpts": [],
        "history": {
            "complete": False,
            "omitted_ranges": [],
            "collection_errors": ["codex transcript not parsed: format unstable"],
            "modalities": [],
        },
        "policy_version": POLICY_VERSION,
        "corpus_version": CORPUS_VERSION,
        "language": "en",
    }

    if event == "UserPromptSubmit":
        envelope["stage"] = "input"
        request = payload.get("prompt")
        if request is None:
            request = payload.get("user_prompt")
        envelope["request"] = request
    elif event == "PreToolUse":
        tool = payload.get("tool_name") or payload.get("tool") or ""
        envelope["stage"] = "pre_action"
        envelope["request"] = f"Tool call: {tool}"
        envelope["proposed_action"] = {
            "tool": tool,
            "arguments": _tool_arguments(payload),
        }
    elif event == "PostToolUse":
        tool = payload.get("tool_name") or payload.get("tool") or ""
        envelope["stage"] = "output"
        envelope["request"] = f"Tool call: {tool}"
        envelope["candidate_response"] = _stringify(payload.get("tool_response"))
    elif event == "Stop":
        envelope["stage"] = "output"
        envelope["request"] = ""
        message = payload.get("last_assistant_message")
        envelope["candidate_response"] = message if message is not None else ""
    else:
        return None

    try:
        validate_envelope(envelope)
    except (EnvelopeError, ValueError):
        return None
    return envelope


def decide(assess_result: dict, payload: dict) -> dict | None:
    """AssessResult + original hook payload -> Codex protocol JSON or None.

    Mapping (v1): see docs/hosts/codex.md. None means "no output" — the
    hook interferes with nothing (proceed everywhere, and PostToolUse/Stop
    below refuse, which are post-hoc only).
    """
    event = payload.get("hook_event_name")
    action = assess_result.get("action")
    text = _guidance_text(assess_result)

    if event == "PreToolUse":
        if action in _BLOCKING_ACTIONS:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": text[:REASON_MAX],
                    "additionalContext": text,
                }
            }
        if action == "guide":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "additionalContext": text,
                }
            }
        return None

    if event == "UserPromptSubmit":
        if action in _BLOCKING_ACTIONS:
            return {"decision": "block", "reason": text}
        if action == "guide":
            return {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": text,
                }
            }
        return None

    if event in ("PostToolUse", "Stop"):
        if action == "refuse":
            return {
                "hookSpecificOutput": {
                    "hookEventName": event,
                    "additionalContext": text,
                }
            }
        return None

    return None


def _run_cli(envelope: dict) -> dict:
    """Default runner: spawn the frozen CLI, parse its AssessResult line.

    Raises on any failure (non-zero exit, timeout, unparseable stdout) so
    main() can fail open with a stderr diagnostic. PEA_BACKEND/PEA_DB/
    PEA_POLICY are passed through as CLI flags; the child inherits the
    environment. stdlib + package-core only: no mcp/ollama import here.
    """
    cmd = [sys.executable, "-m", "patristic_ethics.cli", "assess", "--stdin"]
    if os.environ.get("PEA_BACKEND"):
        cmd += ["--backend", os.environ["PEA_BACKEND"]]
    if os.environ.get("PEA_DB"):
        cmd += ["--db", os.environ["PEA_DB"]]
    if os.environ.get("PEA_POLICY"):
        cmd += ["--policy", os.environ["PEA_POLICY"]]
    proc = subprocess.run(
        cmd,
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        timeout=CLI_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"pea cli exit {proc.returncode}: {proc.stderr.strip()[:200]}"
        )
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("action"), str):
            return obj
    raise RuntimeError("no AssessResult JSON line on cli stdout")


def handle(payload: dict, runner=None) -> dict | None:
    """Offline-testable core: hook payload -> protocol dict, or None.

    Never prints. ``runner`` receives the built envelope dict and returns
    an AssessResult dict; a ``runner`` result without a string ``action``
    is treated as a failure (fail-open -> None). Runner exceptions
    propagate to main(), which fails open with a stderr diagnostic.
    """
    envelope = build_envelope(payload)
    if envelope is None:
        return None
    if runner is None:
        runner = _run_cli  # module global: tests inject a fake here
    result = runner(envelope)
    if not isinstance(result, dict) or not isinstance(result.get("action"), str):
        return None
    return decide(result, payload)


def main(argv: list[str] | None = None) -> int:
    """Hook entry point. Codex passes the payload on stdin; argv is unused.

    Every failure path (malformed stdin, runner failure, runner timeout)
    exits 0 with NO stdout — documented fail-open; Codex must never treat
    a PEA problem as a block. Stdout carries at most one protocol line.
    """
    del argv  # hook commands take no arguments; parity with cli.main
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
    except (OSError, ValueError) as e:
        print(f"pea-codex: malformed hook payload (fail-open): {e}", file=sys.stderr)
        return 0
    try:
        out = handle(payload)
    except Exception as e:  # runner failure/timeout -> fail-open
        print(f"pea-codex: assess failed (fail-open): {e}", file=sys.stderr)
        return 0
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())