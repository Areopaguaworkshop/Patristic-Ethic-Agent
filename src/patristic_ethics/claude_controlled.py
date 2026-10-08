"""PEA-controlled Claude Code client (tools disabled, output buffered)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

from .cli import positive_context_length
from .controlled import HOST_CONTEXT_PROMPT, ControlledClient, HostOutput

HOST_VERSION = "2.1.287"


def parse_claude_stdout(stdout: str) -> HostOutput:
    """Accept only Claude's successful JSON result envelope."""
    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        return HostOutput(failure="Claude Code stdout was not one JSON result")
    if not isinstance(result, dict) or result.get("type") != "result":
        return HostOutput(failure="Claude Code stdout was not a result object")
    if (
        result.get("subtype") != "success"
        or result.get("is_error") is not False
        or not isinstance(result.get("result"), str)
    ):
        return HostOutput(failure="Claude Code returned an error or missing result")
    return HostOutput(text=result["result"])


def claude_runner(
    prompt: str, *, workdir: str, timeout_s: float = 600.0,
    executable: str = "claude",
) -> HostOutput:
    """Run Claude without tools or persisted candidate history, buffering output."""
    command = [
        executable,
        "--print",
        "--safe-mode",
        "--append-system-prompt",
        HOST_CONTEXT_PROMPT,
        "--no-session-persistence",
        "--output-format",
        "json",
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        "{}",
    ]
    try:
        proc = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=workdir,
        )
    except FileNotFoundError:
        return HostOutput(failure="claude executable not found on PATH")
    except subprocess.TimeoutExpired:
        return HostOutput(failure=f"Claude Code timed out after {timeout_s}s")
    if proc.returncode != 0:
        return HostOutput(failure=f"Claude Code exited {proc.returncode}")
    return parse_claude_stdout(proc.stdout)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pea-controlled-claude",
        description="PEA-controlled Claude Code dialogue; only reviewed text reaches stdout.",
    )
    parser.add_argument("--revise-once", action="store_true", help="opt in to one fresh host revision, rechecked before release")
    parser.add_argument("--prompt", help="first prompt; optional with --interactive")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--dir", default=".", help="Claude Code working directory")
    parser.add_argument("--backend", choices=["fake", "ollama"], required=True)
    parser.add_argument("--db", default="corpus/units.db")
    parser.add_argument("--policy", default="policy/rules.json")
    parser.add_argument("--interpreter-model", default="ornith-1.5:9b")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--interpreter-context-length", type=positive_context_length, default=None,
                        help="PEA Ollama context length; does not configure Claude")
    parser.add_argument("--interpreter-thinking", choices=["model-default", "on", "off"],
                        default="model-default", help="PEA Ollama thinking mode")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.interactive and not args.prompt:
        parser.error("--prompt is required unless --interactive is set")
    client = ControlledClient(
        allow_revision=args.revise_once,
        runner=lambda prompt, session_id=None: claude_runner(
            prompt, workdir=args.dir, timeout_s=args.timeout
        ),
        backend=args.backend,
        db_path=args.db,
        policy_path=args.policy,
        interpreter_model=args.interpreter_model,
        host=args.ollama_host,
        timeout_s=args.timeout,
        interpreter_context_length=args.interpreter_context_length,
        interpreter_think={"model-default": None, "on": True, "off": False}[args.interpreter_thinking],
        host_name="claude-code",
        host_version=HOST_VERSION,
    )
    prompt = args.prompt
    while True:
        if prompt is None:
            if not args.interactive:
                break
            sys.stderr.write("you> ")
            sys.stderr.flush()
            line = sys.stdin.readline()
            if not line:
                break
            prompt = line.rstrip("\n")
        if args.interactive and prompt.strip().lower() in {"/quit", "/exit"}:
            break
        result = client.run(prompt)
        print(result.released_text)
        print(
            json.dumps({
                "model_invoked": result.model_invoked,
                "action": result.action,
                "failure": result.failure,
                "audit": result.audit,
            }, ensure_ascii=False),
            file=sys.stderr,
        )
        if not args.interactive:
            break
        prompt = None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
