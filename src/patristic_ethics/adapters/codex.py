"""PEA native Codex adapter (Codex CLI 0.160.0 hooks).

Runs as a Codex hook command: reads ONE hook JSON payload from stdin,
maps it to a ContextEnvelope, spawns the frozen PEA CLI
(``python -m patristic_ethics.cli assess --stdin``, 15 s timeout) and
prints ONE Codex hook-protocol JSON line to stdout (exit 0). Diagnostics
go to stderr only — stdout carries protocol output or nothing.

Documented limits of native Codex mode:

- FAIL-CLOSED for supported input and pre-tool events: assessment errors,
  timeouts and malformed results return the host's documented block/deny
  protocol. Malformed hook JSON and unmapped events remain unassessed.
- The transcript is NOT parsed: ``transcript_path`` is documented as NOT
  stable, so only configured hook-observed history is collected;
  ``history.complete`` remains false on Codex.
- Enforcement is best-effort: there is no MessageDisplay event on Codex
  (no before-display guarantee), and host-level hook termination cannot
  be controlled by this process. Strict output guarantees require
  controlled mode / an agent sandbox, not this adapter alone.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

from ..context import EnvelopeError, validate_envelope
from .history import collect, remember
from .result import validate_result

HOST_NAME = "codex"
HOST_VERSION_DEFAULT = "0.160.0"
POLICY_VERSION = "0.1.0"
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
    - Configured hook-observed history supplies prior messages; completeness
      remains false. The unstable Codex transcript is never parsed.
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
        "messages": [],  # populated only from the configured hook history store
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

    collect(envelope)
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
    handle() can block supported input/pre-tool events. PEA_BACKEND/PEA_DB/
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
    for env_name, flag in (
        ("PEA_PROVIDER", "--provider"),
        ("PEA_INTERPRETER_MODEL", "--model"),
        ("PEA_REMOTE_URL", "--remote-url"),
        ("PEA_API_KEY_ENV", "--api-key-env"),
        ("PEA_INTERPRETER_TIMEOUT", "--timeout"),
    ):
        value = os.environ.get(env_name)
        if value:
            cmd += [flag, value]
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

    Runner failures return a blocking protocol for supported input and
    pre-tool events; events that cannot block an already executed tool or
    displayed output remain best-effort.
    """
    envelope = build_envelope(payload)
    if envelope is None:
        return None
    if runner is None:
        runner = _run_cli  # module global: tests inject a fake here
    try:
        result = validate_result(runner(envelope))
    except Exception as exc:
        print(f"pea-codex: assessment failed; blocking supported hook: {exc}", file=sys.stderr)
        return decide({"action": "withhold", "guidance": {"text": "PEA assessment unavailable; this request or tool call is blocked."}}, payload)
    remember({**envelope, "_hook_event": payload.get("hook_event_name"),
              "_hook_event_id": payload.get("turn_id") or payload.get("prompt_id")}, result["action"])
    return decide(result, payload)


def main(argv: list[str] | None = None) -> int:
    """Hook entry point. Codex passes the payload on stdin; argv is unused.

    Supported input and pre-tool events block on assessment failure.
    Malformed input cannot be mapped safely and exits 0 without protocol
    output. Stdout carries at most one protocol line.
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
    except Exception as e:  # malformed adapter state: no trusted event mapping
        print(f"pea-codex: hook failed before a decision: {e}", file=sys.stderr)
        return 0
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
