"""PEA native adapter for Claude Code command hooks (plan §M5).

Claude Code 2.1.286/287 invokes this module as a command hook: the hook
JSON payload arrives on stdin, this adapter maps it to a ContextEnvelope,
assesses it through the frozen PEA CLI (``python -m patristic_ethics.cli
assess --stdin``), and prints the event's hook-protocol JSON (at most one
line) to stdout. All diagnostics go to stderr.

Guarantees and limits (documented, not smoothed over):

- **Fail-closed where the process can respond.** Runner errors and invalid
  results return block/deny decisions for UserPromptSubmit and PreToolUse.
  A host-enforced timeout or malformed payload cannot be mapped by this
  process. Exit code 2 is not used; protocol JSON carries the decision.
- **Transcript not parsed.** ``transcript_path`` is written asynchronously
  and may lag the hook, so it is never read. Configured hook-observed history supplies prior
  messages; ``history.complete`` remains false.
- **MessageDisplay cannot withhold.** ``displayContent`` replaces only
  what the user sees on screen; the model transcript keeps the original
  text. It is advisory display, never an output gate.
- **Strict guarantees require controlled mode.** Withholding content
  before display is not achievable through these hooks; use the PEA
  controlled client (M4b pattern) when a before-display guarantee is
  required.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Callable, Optional

from ..context import validate_envelope
from .history import collect, remember
from .result import validate_result

HOST_NAME = "claude-code"
HOST_VERSION = "2.1.286"
RUNNER_TIMEOUT_S = 15.0
REASON_MAX = 500
_BLOCKING_ACTIONS = frozenset({"refuse", "clarify", "review", "withhold"})
_NO_GUIDANCE = "PEA assessment completed without guidance text."


def _diag(msg: str) -> None:
    print(msg, file=sys.stderr)


def _guidance_text(assess_result: dict) -> str:
    guidance = assess_result.get("guidance")
    text = guidance.get("text") if isinstance(guidance, dict) else None
    return str(text) if text else _NO_GUIDANCE


def _display_text(payload: dict) -> str:
    msg = payload.get("message", "")
    if isinstance(msg, dict):
        msg = msg.get("content") or msg.get("text") or ""
    return str(msg) if msg is not None else ""


def build_envelope(payload: dict) -> Optional[dict]:
    """Map a Claude Code hook payload to a ContextEnvelope dict.

    Returns the validated envelope dict, or None if the payload is not a
    dict, names an unmapped hook event, or fails envelope validation.
    """
    if not isinstance(payload, dict):
        return None
    session_id = str(payload.get("session_id") or "unknown")
    prompt_id = str(payload.get("prompt_id") or "")
    envelope: dict = {
        "schema_version": "1",
        "host": {"name": HOST_NAME, "version": HOST_VERSION, "mode": "native"},
        "session": {"id": session_id},
        "turn": {"id": prompt_id or f"turn-{session_id}", "event_id": prompt_id or None},
        "messages": [],
        "earlier_excerpts": [],
        "history": {"complete": False},
        "policy_version": "draft",
        "corpus_version": "draft",
        "language": "en",
    }
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        envelope["stage"] = "input"
        envelope["request"] = str(payload.get("prompt") or "")
    elif event == "PreToolUse":
        tool = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            tool_input = {}
        envelope["stage"] = "pre_action"
        envelope["request"] = f"Tool call: {tool}"
        envelope["proposed_action"] = {"tool": tool, "arguments": tool_input}
    elif event == "PostToolUse":
        response = payload.get("tool_response")
        envelope["stage"] = "output"
        envelope["request"] = ""
        envelope["candidate_response"] = str(response) if response is not None else ""
    elif event == "Stop":
        message = payload.get("last_assistant_message")
        envelope["stage"] = "output"
        envelope["request"] = ""
        envelope["candidate_response"] = str(message) if message is not None else ""
    elif event == "MessageDisplay":
        envelope["stage"] = "output"
        envelope["request"] = ""
        envelope["candidate_response"] = _display_text(payload)
    else:
        return None
    collect(envelope)
    try:
        validate_envelope(envelope)
    except ValueError:  # EnvelopeError subclasses ValueError
        return None
    return envelope


def decide(assess_result: dict, payload: dict) -> Optional[dict]:
    """Map an AssessResult dict + hook payload to hook-protocol JSON.

    Returns None for proceed (and any unmapped combination): the hook
    prints nothing and the host continues. See docs/hosts/claude-code.md
    for the full event × action table.
    """
    if not isinstance(assess_result, dict) or not isinstance(payload, dict):
        return None
    action = assess_result.get("action")
    event = payload.get("hook_event_name")
    text = _guidance_text(assess_result)

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
    if event in ("PostToolUse", "Stop"):
        if action == "refuse":
            return {"decision": "block", "reason": text}
        return None
    if event == "MessageDisplay":
        if action in ("guide", "refuse"):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "MessageDisplay",
                    "displayContent": f"PEA: {text}",
                }
            }
        return None
    return None


def default_runner(envelope_json: str) -> str:
    """Assess one envelope via the frozen PEA CLI; return its stdout line.

    PEA_BACKEND/PEA_DB/PEA_POLICY are passed through as CLI flags (the
    CLI itself reads no environment). Raises on non-zero exit or timeout;
    `handle()` blocks supported input/pre-tool events on those failures.
    """
    cmd = [
        sys.executable,
        "-m",
        "patristic_ethics.cli",
        "assess",
        "--stdin",
        "--backend",
        os.environ.get("PEA_BACKEND", "fake"),
    ]
    db = os.environ.get("PEA_DB")
    if db:
        cmd += ["--db", db]
    policy = os.environ.get("PEA_POLICY")
    if policy:
        cmd += ["--policy", policy]
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
        input=envelope_json,
        capture_output=True,
        text=True,
        timeout=RUNNER_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"pea cli exited {proc.returncode}: {proc.stderr.strip()[:200]}"
        )
    return proc.stdout


def handle(payload: dict, runner: Callable[[str], str]) -> "tuple[Optional[dict], Optional[str]]":
    """Assess one hook payload: (protocol_output, diagnostic).

    protocol_output None with a diagnostic means fail-open (no stdout).
    protocol_output None without a diagnostic means proceed.
    """
    envelope = build_envelope(payload)
    if envelope is None:
        return None, "pea claude-code: unmapped or invalid hook payload (fail-open)"
    try:
        raw = runner(json.dumps(envelope, ensure_ascii=False))
        assess_result = validate_result(json.loads(raw))
    except Exception as e:  # timeout, non-zero exit, malformed stdout
        event = payload.get("hook_event_name")
        failure = {"action": "withhold", "guidance": {"text": "PEA assessment unavailable; this request or tool call is blocked."}}
        out = decide(failure, payload) if event in ("UserPromptSubmit", "PreToolUse") else None
        return out, f"pea claude-code: assessment failed; supported event blocked: {e}"
    remember({**envelope, "_hook_event": payload.get("hook_event_name"),
              "_hook_event_id": payload.get("turn_id") or payload.get("prompt_id")}, assess_result.get("action", ""))
    return decide(assess_result, payload), None


def main(argv: "Optional[list[str]]" = None, runner: "Optional[Callable[[str], str]]" = None) -> int:
    """Hook entry point: stdin hook JSON -> at most one protocol JSON line.

    Always exits 0: a blocked outcome is expressed by protocol JSON on
    stdout, never by the exit code. argv is accepted for signature
    compatibility; hooks pass nothing.
    """
    del argv  # unused: hooks invoke this module with no arguments
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("expected a JSON object")
    except (OSError, ValueError) as e:
        _diag(f"pea claude-code: malformed hook input (fail-open): {e}")
        return 0
    out, diag = handle(payload, runner or default_runner)
    if diag:
        _diag(diag)
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
