"""Structured interpreter contract and backends (plan §5.3).

The interpreter maps a validated ContextEnvelope to a structured
Observation. It has NO operational tools and NO approval powers.
Schema failure, timeout, or missing backend is an operational
uncertainty (InterpreterUnavailable), never a moral conclusion.
"""

from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.request
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
    assistance_type: Literal[
        "facilitation", "benign_discussion", "support_seeking", "uncertain"
    ] = "uncertain"
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
                return self._with_current_request(observation, envelope)
        return self._with_current_request(self.default, envelope)

    @staticmethod
    def _with_current_request(observation: Observation, envelope: ContextEnvelope) -> Observation:
        result = observation.model_copy(deep=True)
        if not result.evidence and (result.topics or result.assistance_type != "uncertain"):
            source_id = "candidate_response" if envelope.stage == "output" else "current_request"
            source_text = envelope.candidate_response if source_id == "candidate_response" else envelope.request
            result.evidence = [Evidence(source_id=source_id, quote=source_text)] if source_text else []
        return result


_LIST_FIELDS = (
    "affected_parties",
    "topics",
    "benign_explanations",
    "unresolved_ambiguity",
)

_EMPTY_AMBIGUITY = re.compile(
    r"^(?:none|no|n/a|nothing|not ambiguous|no ambiguity|the request is clear)\b",
    re.IGNORECASE,
)


def normalize_observation_payload(payload: dict) -> dict:
    """Tolerate single-string list fields and numeric-string confidence.

    The model still has to produce valid JSON and valid semantic content; this
    only prevents a harmless type drift from becoming a false outage.
    """
    if not isinstance(payload, dict):
        return payload
    data = dict(payload)
    for key in _LIST_FIELDS:
        value = data.get(key)
        if value is None:
            data[key] = []
        elif isinstance(value, str):
            data[key] = [value]
    ambiguity = data.get("unresolved_ambiguity")
    if isinstance(ambiguity, list):
        data["unresolved_ambiguity"] = [
            item for item in ambiguity
            if not (isinstance(item, str) and _EMPTY_AMBIGUITY.match(item.strip()))
        ]
    evidence = data.get("evidence")
    if evidence is None:
        data["evidence"] = []
    elif isinstance(evidence, dict):
        data["evidence"] = [evidence]
    confidence = data.get("confidence")
    if isinstance(confidence, str):
        try:
            data["confidence"] = float(confidence)
        except ValueError:
            data["confidence"] = None
    return data


class OllamaInterpreter:
    """Local Ollama backend. One attempt, no retries, no tools."""

    def __init__(
        self,
        model: str = "deepseek-v4.1-flash:cloud",
        host: str = "http://localhost:11434",
        timeout_s: float = 60.0,
        num_ctx: int | None = None,
        think: bool | None = None,
    ):
        if num_ctx is not None and (type(num_ctx) is not int or num_ctx < 1):
            raise ValueError("num_ctx must be a positive integer")
        if think is not None and not isinstance(think, bool):
            raise ValueError("think must be boolean or None")
        self.model = model
        self.host = host
        self.timeout_s = timeout_s
        self.num_ctx, self.think = num_ctx, think
        self.last_usage: dict[str, int | None] | None = None
        self.schema = Observation.model_json_schema()
        # Older saved observations remain loadable for offline compatibility,
        # but live structured outputs must explicitly classify the request.
        if "assistance_type" not in self.schema["required"]:
            self.schema["required"].append("assistance_type")
        # ponytail: cap array sizes so the grammar can't run away; raise if
        # evaluation ever needs longer evidence lists.
        for key in ("affected_parties", "topics", "benign_explanations", "unresolved_ambiguity"):
            self.schema["properties"][key]["maxItems"] = 10
        self.schema["properties"]["evidence"]["maxItems"] = 10
        self.schema["properties"]["evidence"]["minItems"] = 1
        import httpx
        import ollama

        self._httpx = httpx
        self._ollama = ollama
        self._client = ollama.Client(host=host, timeout=timeout_s)

    _TASK = (
        "You observe a conversation for an ethics review layer. Describe the "
        "assistance being requested as JSON with these fields:\n"
        "- requested_assistance: one sentence, what help is being asked for\n"
        "- assistance_type: exactly one of facilitation, benign_discussion, "
        "support_seeking, uncertain. Use facilitation only when the requested "
        "help would materially enable harm; benign analysis, prevention, study, "
        "quotation and technical meanings are benign_discussion; distress "
        "disclosure without harmful means is support_seeking; if missing context could "
        "change the decision use uncertain and name the missing antecedent; never invent it\n"
        "- affected_parties: who could be harmed or helped (short labels)\n"
        "- topics: short topic labels\n"
        "- expressed_intent: the user's expressed intent, taken from the text only\n"
        "- evidence: [{\"source_id\": ..., \"quote\": ...}] quoting the relevant "
        "context verbatim; include at least one item and use only source_ids "
        "that appear in the context\n"
        "- benign_explanations: plausible innocent readings, if any\n"
        "- unresolved_ambiguity: what is unclear, if anything\n"
        "- confidence: 0 to 1, or null\n"
        "Quote verbatim, do not invent sources, judge only what is expressed."
    )

    def _prompt(self, envelope: ContextEnvelope) -> str:
        return build_prompt(envelope, self._TASK)

    def interpret(self, envelope: ContextEnvelope) -> Observation:
        self.last_usage = None
        try:
            options = {"temperature": 0, "num_predict": 2048}
            if self.num_ctx is not None:
                options["num_ctx"] = self.num_ctx
            thinking = {} if self.think is None else {"think": self.think}
            response = self._client.chat(
                model=self.model,
                messages=[{"role": "user", "content": self._prompt(envelope)}],
                format=self.schema,
                options=options,
                **thinking,
            )
            self.last_usage = {
                "prompt_tokens": getattr(response, "prompt_eval_count", None),
                "completion_tokens": getattr(response, "eval_count", None),
            }
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
            parsed = normalize_observation_payload(json.loads(content))
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


def build_prompt(envelope: ContextEnvelope, task: str) -> str:
    """Shared flat-text prompt for local and remote interpreters."""
    lines = [
        "History metadata (adapter supplied): "
        + json.dumps(envelope.history.model_dump(), ensure_ascii=False),
        f"Message current_request (role=user, origin=user, stage={envelope.stage}): "
        f"{envelope.request}",
    ]
    for message in envelope.messages:
        lines.append(
            f"Message {message.source_id} (role={message.role}, origin={message.origin}): {message.text}"
        )
    for excerpt in envelope.earlier_excerpts:
        lines.append(f"Earlier excerpt {excerpt.source_id}: {excerpt.text}")
    if envelope.summary:
        lines.append(
            f"Summary {envelope.summary.source_id} "
            f"(refs={json.dumps(envelope.summary.refs)}): {envelope.summary.text}"
        )
    if envelope.proposed_action:
        action = envelope.proposed_action
        action_text = (
            f"{action.tool} "
            f"{json.dumps(action.arguments, sort_keys=True, ensure_ascii=False)}"
        )
        lines.append(f"Message proposed_action (role=tool, origin=tool): {action_text}")
    if envelope.candidate_response:
        lines.append(f"Candidate response: {envelope.candidate_response}")
    lines.append(task)
    return "\n".join(lines)


# Provider presets. API keys are read from the environment; never pass them
# on the command line or write them to logs.
PROVIDERS: dict[str, dict[str, str | None]] = {
    "openai": {
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": None,
    },
    "deepseek": {
        "kind": "openai",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "openrouter": {
        "kind": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "default_model": None,
    },
    "groq": {
        "kind": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_env": "GROQ_API_KEY",
        "default_model": None,
    },
    "together": {
        "kind": "openai",
        "base_url": "https://api.together.xyz/v1",
        "api_key_env": "TOGETHER_API_KEY",
        "default_model": None,
    },
    "anthropic": {
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": None,
    },
    "custom": {
        "kind": "openai",
        "base_url": None,
        "api_key_env": "PEA_REMOTE_API_KEY",
        "default_model": None,
    },
}


class RemoteInterpreter:
    """OpenAI-compatible or Anthropic remote backend. One attempt, no tools."""

    def __init__(
        self,
        provider: str = "openai",
        model: str | None = None,
        base_url: str | None = None,
        api_key_env: str | None = None,
        timeout_s: float = 8.0,
        json_mode: bool = True,
        max_tokens: int = 512,
        api_key: str | None = None,
    ):
        provider = provider.casefold()
        if provider not in PROVIDERS:
            raise ValueError(
                f"unknown provider {provider!r}; choose one of {sorted(PROVIDERS)}"
            )
        config = PROVIDERS[provider]
        self.provider = provider
        self.kind = str(config["kind"])
        self.model = model or config.get("default_model")
        if not self.model:
            raise ValueError(f"{provider} requires an explicit model")
        self.base_url = (base_url or config.get("base_url") or "").rstrip("/")
        if not self.base_url:
            raise ValueError("custom provider requires a base_url")
        env_name = api_key_env or str(config["api_key_env"])
        key = api_key if api_key is not None else os.environ.get(env_name, "")
        if not key:
            raise ValueError(f"{env_name} is not set")
        self._key = key
        self._env_name = env_name
        self.timeout_s = timeout_s
        self.json_mode = json_mode
        self.max_tokens = max_tokens
        self.last_usage: dict[str, int | None] | None = None

    def _post(self, path: str, payload: dict, headers: dict[str, str]) -> dict:
        url = self.base_url + path
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read(1000).decode("utf-8", errors="replace")
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason=f"{self.provider} HTTP {exc.code}",
                    detail=body[:300],
                    kind="other",
                )
            ) from exc
        except (socket.timeout, TimeoutError) as exc:
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason=f"{self.provider} call timed out",
                    detail=str(exc),
                    kind="timeout",
                )
            ) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise InterpreterUnavailable(
                    InterpreterFailure(
                        reason=f"{self.provider} call timed out",
                        detail=str(exc.reason),
                        kind="timeout",
                    )
                ) from exc
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason=f"{self.provider} connection failed",
                    detail=str(exc.reason),
                    kind="connection",
                )
            ) from exc
        except Exception as exc:
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason=f"{self.provider} call failed: {type(exc).__name__}",
                    detail=str(exc),
                    kind="other",
                )
            ) from exc

    @staticmethod
    def _content(value) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = []
            for part in value:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            return "".join(parts)
        return ""

    def _parse(self, content: str) -> Observation:
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            parsed = normalize_observation_payload(json.loads(text))
        except json.JSONDecodeError as exc:
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason="model output is not valid JSON",
                    detail=str(exc),
                    kind="schema",
                )
            ) from exc
        try:
            return Observation.model_validate(parsed)
        except ValidationError as exc:
            raise InterpreterUnavailable(
                InterpreterFailure(
                    reason="model output does not match the Observation schema",
                    detail=str(exc.errors()),
                    kind="schema",
                )
            ) from exc

    def interpret(self, envelope: ContextEnvelope) -> Observation:
        self.last_usage = None
        prompt = build_prompt(envelope, OllamaInterpreter._TASK)
        if self.kind == "anthropic":
            payload = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "temperature": 0,
                "system": OllamaInterpreter._TASK,
                "messages": [{"role": "user", "content": prompt}],
            }
            data = self._post(
                "/messages",
                payload,
                {
                    "x-api-key": self._key,
                    "anthropic-version": "2023-06-01",
                },
            )
            usage = data.get("usage") or {}
            self.last_usage = {
                "prompt_tokens": usage.get("input_tokens"),
                "completion_tokens": usage.get("output_tokens"),
            }
            content = self._content(data.get("content"))
        else:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": OllamaInterpreter._TASK},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
                "max_tokens": self.max_tokens,
            }
            if self.json_mode:
                payload["response_format"] = {"type": "json_object"}
            data = self._post(
                "/chat/completions",
                payload,
                {"Authorization": f"Bearer {self._key}"},
            )
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise InterpreterUnavailable(
                    InterpreterFailure(
                        reason=f"{self.provider} response has no message content",
                        detail=str(exc),
                        kind="schema",
                    )
                ) from exc
            usage = data.get("usage") or {}
            self.last_usage = {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
            }
        return self._parse(self._content(content))
