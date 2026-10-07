"""PEA-owned controlled client for the OpenCode vertical slice.

Implements plan §4 controlled mode and §M4 item 2. The controlled client —
not a host plugin — owns the display: it spawns `opencode run --format json`,
buffers ALL host stdout in memory (never printing while the host runs), and
releases only the text PEA approves after its output assessment.

Honest boundary (first slice, tools disabled):
- Tools are disabled via host project config `"tools": {"*": false}`
  (examples/opencode/controlled/opencode.json). That gate is host-documented,
  not probe-verified, and PEA cannot confirm at runtime that the host honored
  it; see docs/hosts/opencode.md for the residual risk.
- The host still persists its own session store; this boundary covers THIS
  client's stdout only.
- This module invokes the HOST, never the PEA plugin. Do not combine the
  native plugin and this client in one profile (duplicate assessment; no
  shared private call path yet — M4 item 4 is future work).

Documented v1 choices:
- Each run() is a fresh single-shot session: the envelope records
  history.complete=False with collection_errors=["fresh session"]; prior
  turns are not collected (multi-turn collection is later work).
- On input action "guide" the host IS invoked and display follows the OUTPUT
  assessment; the input guidance is kept in input_assessment, not released.
- On output refuse/guide/clarify/review, PEA guidance text replaces the
  buffered host text in the display (the buffer is discarded from release).
- `ControlledResult.buffered` retains the raw host text in memory for audit
  only; this module never writes it to disk.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from typing import Callable

from .assess import AssessResult, assess
from .context import ContextEnvelope, build_envelope
from .corpus import sha256_text
from .interpreter import FakeInterpreter, OllamaInterpreter
from .policy import load_policy

HOST_NAME = "opencode"
HOST_VERSION = "1.18.34"  # probed version (docs/host-coverage.md)
HOST_MODE = "controlled"
DEFAULT_CORPUS_VERSION = "0.1.0-draft"
DEFAULT_DB = "corpus/units.db"
DEFAULT_POLICY = "policy/rules.json"
# Grammar-capable per probe S1: ornith-1.5:9b fails OpenCode's tool schema.
DEFAULT_HOST_MODEL = "ollama/deepseek-v4.1-flash:cloud"
DEFAULT_INTERPRETER_MODEL = "ornith-1.5:9b"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT = 600.0

WITHHELD_MESSAGE = (
    "PEA could not complete its review; this response was withheld. "
    "No judgment about the user is implied."
)

# AssessResult actions that stop the host from being invoked at all.
_STOP_ACTIONS = ("refuse", "clarify", "review", "withhold")
# Output actions that release the buffered host text unchanged.
_RELEASE_ACTIONS = ("proceed",)


@dataclass
class HostOutput:
    """One host run's raw result.

    `text` is the concatenated text parts, buffered in memory (this module
    never prints it). `failure` is None only when the host exited 0 and
    every non-blank stdout line parsed as a JSON event.
    """

    text: str = ""
    failure: str | None = None


@dataclass
class ControlledResult:
    model_invoked: bool
    action: str
    released_text: str
    input_assessment: AssessResult
    output_assessment: AssessResult | None = None
    buffered: str = ""  # raw host text; in-memory audit only
    failure: str | None = None
    audit: dict = field(default_factory=dict)


def parse_host_stdout(stdout: str) -> HostOutput:
    """Parse `opencode run --format json` stdout into buffered text.

    Text parts (event type "text" with part.type "text") are concatenated in
    event order. Any non-blank line that is not a JSON object is a failure:
    content that cannot be parsed cannot be verified as non-display text, so
    the whole run is withheld rather than partially released.
    """
    parts: list[str] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return HostOutput(
                failure=f"stdout line is not a JSON event: {line.strip()[:120]}"
            )
        if not isinstance(event, dict):
            return HostOutput(failure="stdout line is not a JSON object")
        part = event.get("part")
        if (
            event.get("type") == "text"
            and isinstance(part, dict)
            and part.get("type") == "text"
        ):
            parts.append(str(part.get("text", "")))
    return HostOutput(text="".join(parts))


def opencode_runner(
    prompt: str, *, workdir: str, model: str, timeout_s: float = DEFAULT_TIMEOUT
) -> HostOutput:
    """Default runner: spawn `opencode run` and buffer ALL output in memory.

    Nothing here is printed. PEA_CONTROLLED=1 marks the child environment.
    A missing executable, non-zero exit, timeout, or unparseable stdout is a
    failure; the caller then withholds (an executor failure never releases).
    """
    argv = [
        "opencode", "run", "--dir", str(workdir),
        "--format", "json", "-m", model, prompt,
    ]
    env = {**os.environ, "PEA_CONTROLLED": "1"}
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout_s, env=env
        )
    except FileNotFoundError:
        return HostOutput(failure="opencode executable not found on PATH")
    except subprocess.TimeoutExpired:
        return HostOutput(failure=f"opencode run timed out after {timeout_s}s")
    if proc.returncode != 0:
        stderr_tail = ""
        stripped = (proc.stderr or "").strip()
        if stripped:
            stderr_tail = stripped.splitlines()[-1][:200]
        return HostOutput(
            failure=f"opencode run exited {proc.returncode}"
            + (f": {stderr_tail}" if stderr_tail else "")
        )
    return parse_host_stdout(proc.stdout)


def _released_text(result: AssessResult) -> str:
    """PEA-authored text for a non-release action: the composed guidance
    when present, else the static withheld message."""
    if result.guidance is not None and result.guidance.text:
        return result.guidance.text
    return WITHHELD_MESSAGE


class ControlledClient:
    """Buffers all host display content until PEA review completes.

    runner: callable(prompt) -> HostOutput (default: `opencode run`
    subprocess via opencode_runner). assessor: callable(envelope) ->
    AssessResult (default: assess() with the configured interpreter, policy
    and corpus db). Both are injectable for offline tests.
    """

    def __init__(
        self,
        *,
        runner: Callable[[str], HostOutput] | None = None,
        assessor: Callable[[ContextEnvelope], AssessResult] | None = None,
        policy_version: str = "",
        corpus_version: str = DEFAULT_CORPUS_VERSION,
        workdir: str = ".",
        host_model: str = DEFAULT_HOST_MODEL,
        backend: str = "fake",
        db_path: str = DEFAULT_DB,
        policy_path: str = DEFAULT_POLICY,
        interpreter_model: str = DEFAULT_INTERPRETER_MODEL,
        host: str = DEFAULT_OLLAMA_HOST,
        timeout_s: float = DEFAULT_TIMEOUT,
    ):
        self.corpus_version = corpus_version
        self.runner = runner or (
            lambda prompt: opencode_runner(
                prompt, workdir=workdir, model=host_model, timeout_s=timeout_s
            )
        )
        if assessor is not None:
            self.assessor = assessor
            self.policy_version = policy_version
        else:
            policy_doc = load_policy(policy_path)
            self.policy_version = (
                policy_version or policy_doc.get("policy_version", "")
            )
            interpreter = (
                FakeInterpreter([])
                if backend == "fake"
                else OllamaInterpreter(
                    model=interpreter_model, host=host, timeout_s=timeout_s
                )
            )

            def _assessor(envelope: ContextEnvelope) -> AssessResult:
                return assess(
                    envelope,
                    interpreter=interpreter,
                    policy_doc=policy_doc,
                    db_path=db_path,
                    corpus_version=envelope.corpus_version,
                )

            self.assessor = _assessor

    def _envelope(
        self, *, stage: str, prompt: str, session_id: str, candidate: str | None
    ) -> ContextEnvelope:
        # v1: fresh single-shot session — history honestly marked incomplete.
        return build_envelope(
            host={"name": HOST_NAME, "version": HOST_VERSION, "mode": HOST_MODE},
            session={"id": session_id},
            turn={"id": f"turn-{uuid.uuid4().hex[:12]}"},
            stage=stage,
            request=prompt,
            candidate_response=candidate,
            history={"complete": False, "collection_errors": ["fresh session"]},
            policy_version=self.policy_version,
            corpus_version=self.corpus_version,
        )

    def run(self, prompt: str, *, session_id: str | None = None) -> ControlledResult:
        """Assess the prompt, run the host only if allowed, and assess the
        buffered output before releasing anything. Never prints."""
        session = session_id or f"controlled-{uuid.uuid4().hex[:12]}"
        in_res = self.assessor(
            self._envelope(stage="input", prompt=prompt, session_id=session, candidate=None)
        )

        if in_res.action in _STOP_ACTIONS:
            # refuse/clarify/review/withhold: the host model is never invoked;
            # PEA's own text is released instead.
            return self._finish(
                model_invoked=False,
                action=in_res.action,
                released=_released_text(in_res),
                input_assessment=in_res,
                output_assessment=None,
                buffered="",
                failure=None,
                session=session,
                prompt=prompt,
            )

        try:
            out = self.runner(prompt)
        except Exception as e:  # executor failure: withhold, never release
            out = HostOutput(failure=f"host runner raised {type(e).__name__}: {e}")
        if out.failure is not None:
            return self._finish(
                model_invoked=True,
                action="withhold",
                released=WITHHELD_MESSAGE,
                input_assessment=in_res,
                output_assessment=None,
                buffered=out.text,
                failure=out.failure,
                session=session,
                prompt=prompt,
            )

        out_res = self.assessor(
            self._envelope(
                stage="output", prompt=prompt, session_id=session, candidate=out.text
            )
        )
        if out_res.action in _RELEASE_ACTIONS:
            released = out.text
        else:
            # refuse -> composed guidance (buffered discarded from display);
            # guide/clarify/review -> guidance replaces buffered (documented);
            # withhold -> static service message.
            released = _released_text(out_res)
        return self._finish(
            model_invoked=True,
            action=out_res.action,
            released=released,
            input_assessment=in_res,
            output_assessment=out_res,
            buffered=out.text,
            failure=None,
            session=session,
            prompt=prompt,
        )

    def _finish(
        self,
        *,
        model_invoked: bool,
        action: str,
        released: str,
        input_assessment: AssessResult,
        output_assessment: AssessResult | None,
        buffered: str,
        failure: str | None,
        session: str,
        prompt: str,
    ) -> ControlledResult:
        return ControlledResult(
            model_invoked=model_invoked,
            action=action,
            released_text=released,
            input_assessment=input_assessment,
            output_assessment=output_assessment,
            buffered=buffered,
            failure=failure,
            audit={
                "session": session,
                "prompt_digest": sha256_text(prompt),
                "policy_version": self.policy_version,
                "corpus_version": self.corpus_version,
                "buffered_chars": len(buffered),
                "released_chars": len(released),
            },
        )


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="patristic-ethics-controlled",
        description=(
            "PEA controlled client for OpenCode (M4b, tools-disabled first "
            "slice). Stdout receives only the released text; diagnostics go "
            "to stderr."
        ),
    )
    p.add_argument("--prompt", required=True)
    p.add_argument(
        "--dir", default=".",
        help="host working directory (place the controlled opencode.json there)",
    )
    p.add_argument(
        "--model", required=True,
        help="host model for `opencode run -m` (e.g. ollama/deepseek-v4.1-flash:cloud)",
    )
    p.add_argument(
        "--backend", choices=["fake", "ollama"], default="fake",
        help="PEA interpreter backend (default: fake)",
    )
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--policy", default=DEFAULT_POLICY)
    p.add_argument("--interpreter-model", default=DEFAULT_INTERPRETER_MODEL)
    p.add_argument("--host", default=DEFAULT_OLLAMA_HOST)
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    return p


def main(argv: list[str] | None = None) -> int:
    """CLI wrapper: stdout carries ONLY the released text (the controlled
    display); diagnostics go to stderr. Exit 0 covers released and withheld
    outcomes alike (a withheld message is a successful gate, not a crash);
    setup failures exit 1."""
    args = _parser().parse_args(argv)
    try:
        client = ControlledClient(
            workdir=args.dir,
            host_model=args.model,
            backend=args.backend,
            db_path=args.db,
            policy_path=args.policy,
            interpreter_model=args.interpreter_model,
            host=args.host,
            timeout_s=args.timeout,
        )
    except Exception as e:  # policy load or backend construction failure
        print(json.dumps({"error": "setup failed", "detail": str(e)}), file=sys.stderr)
        return 1

    result = client.run(args.prompt)
    print(result.released_text)  # the controlled display
    print(
        json.dumps(
            {
                "model_invoked": result.model_invoked,
                "action": result.action,
                "failure": result.failure,
                "audit": result.audit,
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())