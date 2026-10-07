"""Structured interpreter contract and backends (plan §5.3).

The interpreter maps a validated ContextEnvelope to a structured
Observation. It has NO operational tools and NO approval powers.
Schema failure, timeout, or missing backend is an operational
uncertainty (InterpreterUnavailable), never a moral conclusion.
"""

from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Literal, Protocol, Union

from pydantic import BaseModel, Field, ValidationError

from .context import ContextEnvelope

FailureKind = Literal["timeout", "connection", "schema", "other"]


class Evidence(BaseModel):
    """Points to an actual envelope source_id; the quote is verbatim data."""

    source_id: str
    quote: str


class Observation(BaseModel):
    """Structured observation of the assistance being requested."""

    requested_assistance: str
    affected_parties: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    expressed_intent: str
    evidence: list[Evidence] = Field(default_factory=list)
    benign_explanations: list[str] = Field(default_factory=list)
    unresolved_ambiguity: list[str] = Field(default_factory=list)
    confidence: Union[float, None] = Field(default=None, ge=0.0, le=1.0)


@dataclass
class InterpreterFailure:
    reason: str
    detail: Union[str, None] = None
    kind: FailureKind = "other"


class InterpreterUnavailable(Exception):
    """Operational failure: the interpreter could not produce an Observation."""

    def __init__(self, failure: InterpreterFailure):
        super().__init__(f"{failure.kind}: {failure.reason}")
        self.failure = failure


class Interpreter(Protocol):
    def interpret(self, envelope: ContextEnvelope) -> Observation:
        ...


class FakeInterpreter:
    """Deterministic offline backend: substring-match on envelope.request.

    script maps a substring to an Observation; the first match wins.
    No match -> benign default observation. Counts calls for tests.
    """

    def __init__(
        self,
        script: Union[dict[str, Observation], list[tuple[str, Observation]]],
        default: Union[Observation, None] = None,
    ):
        self.script: list[tuple[str, Observation]] = (
            list(script.items()) if isinstance(script, dict) else list(script)
        )
        self.default = default or Observation(
            requested_assistance="ordinary work",
            affected_parties=[],
            topics=[],
            expressed_intent="benign",
            evidence=[],
            benign_explanations=["no scripted match; defaulting to benign"],
            unresolved_ambiguity=[],
            confidence=None,
        )
        self.calls = 0

    def interpret(self, envelope: ContextEnvelope) -> Observation:
        self.calls += 1
        for substring, observation in self.script:
            if substring in envelope.request:
                return observation.model_copy(deep=True)
        return self.default.model_copy(deep=True)


class OllamaInterpreter:
    """Local Ollama backend. One attempt, no retries, no tools."""

    def __init__(
        self,
        model: str = "ornith-1.5:9b",
        host: str = "http://localhost:11434",
        timeout_s: float = 60.0,
    ):
        self.model = model
        self.host = host
        self.timeout_s = timeout_s
        self.schema = Observation.model_json_schema()
        # ponytail: cap array sizes so the grammar can't run away; raise if
        # evaluation ever needs longer evidence lists.
        for key in ("affected_parties", "topics", "benign_explanations", "unresolved_ambiguity"):
            self.schema["properties"][key]["maxItems"] = 10
        self.schema["properties"]["evidence"]["maxItems"] = 10
        import httpx
        import ollama

        self._httpx = httpx
        self._ollama = ollama
        self._client = ollama.Client(host=host, timeout=timeout_s)

    _TASK = (
        "You observe a conversation for an ethics review layer. Describe the "
        "assistance being requested as JSON with these fields:\n"
        "- requested_assistance: one sentence, what help is being asked for\n"
        "- affected_parties: who could be harmed or helped (short labels)\n"
        "- topics: short topic labels\n"
        "- expressed_intent: the user's expressed intent, taken from the text only\n"
        "- evidence: [{\"source_id\": ..., \"quote\": ...}] quoting the relevant "
        "context verbatim; use only source_ids that appear in the context\n"
        "- benign_explanations: plausible innocent readings, if any\n"
        "- unresolved_ambiguity: what is unclear, if anything\n"
        "- confidence: 0 to 1, or null\n"
        "Quote verbatim, do not invent sources, judge only what is expressed."
    )

    def _prompt(self, envelope: ContextEnvelope) -> str:
        # ponytail: flat text serialization; adapters may refine later.
        lines = [f"Current request (stage {envelope.stage}): {envelope.request}"]
        for m in envelope.messages:
            lines.append(f"Message {m.source_id} (role={m.role}, origin={m.origin}): {m.text}")
        for e in envelope.earlier_excerpts:
            lines.append(f"Earlier excerpt {e.source_id}: {e.text}")
        if envelope.summary:
            lines.append(f"Summary: {envelope.summary.text}")
        if envelope.proposed_action:
            lines.append(f"Proposed action: {envelope.proposed_action.tool} {envelope.proposed_action.arguments}")
        if envelope.candidate_response:
            lines.append(f"Candidate response: {envelope.candidate_response}")
        lines.append(self._TASK)
        return "\n".join(lines)

    def interpret(self, envelope: ContextEnvelope) -> Observation:
        try:
            response = self._client.chat(
                model=self.model,
                messages=[{"role": "user", "content": self._prompt(envelope)}],
                format=self.schema,
                options={"temperature": 0, "num_predict": 512},
            )
            content = response.message.content
        except ConnectionError as e:
            raise InterpreterUnavailable(
                InterpreterFailure(reason="ollama connection failed", detail=str(e), kind="connection")
            ) from e
        except self._ollama.ResponseError as e:
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason=f"ollama request failed: {e.error}",
                    detail=f"status {getattr(e, 'status_code', None)}",
                    kind="other",
                )
            ) from e
        except self._httpx.TimeoutException as e:
            raise InterpreterUnavailable(
                InterpreterFailure(reason="ollama call timed out", detail=str(e), kind="timeout")
            ) from e
        except Exception as e:
            raise InterpreterUnavailable(
                InterpreterFailure(reason=f"ollama call failed: {type(e).__name__}", detail=str(e), kind="other")
            ) from e

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason="model output is not valid JSON",
                    detail=str(e),
                    kind="schema",
                )
            ) from e
        try:
            return Observation.model_validate(parsed)
        except ValidationError as e:
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason="model output does not match the Observation schema",
                    detail=str(e.errors()),
                    kind="schema",
                )
            ) from e