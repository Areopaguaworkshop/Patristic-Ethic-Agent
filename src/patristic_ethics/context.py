"""Context envelope contract (plan §5.2).

The ContextEnvelope is the single validated unit of conversation context
passed from a host adapter to the assessment core. The host adapter
supplies the trusted fields; conversation text inside the envelope is
untrusted data.

Trust boundary: `schema_version`, `host`, `session`, `turn`, `stage`,
`policy_version`, `corpus_version`, `language`, and `history` are trusted
fields supplied only by the host adapter. The text inside `request`,
`messages`, `earlier_excerpts`, `summary`, `proposed_action.arguments`,
and `candidate_response` is DATA: it is never interpreted as a developer
instruction, never overrides a trusted field, and never changes the
stage or the assessment's authority. Adapters must not accept arbitrary
filesystem transcript paths from a remote MCP caller.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

Stage = Literal["input", "pre_action", "output"]
MessageRole = Literal["user", "assistant", "tool", "system"]
MessageOrigin = Literal["user", "assistant", "tool", "summary", "attachment", "quote"]


class EnvelopeError(ValueError):
    """Raised when envelope data does not satisfy the context contract."""

    def __init__(self, message: str, errors: Optional[list[str]] = None):
        super().__init__(message)
        self.errors: list[str] = errors or []


class Host(BaseModel):
    name: str
    version: str
    mode: str


class Session(BaseModel):
    id: str
    parent_id: Optional[str] = None


class Turn(BaseModel):
    id: str
    event_id: Optional[str] = None


class Message(BaseModel):
    # `text` is untrusted data; role/source_id/seq/origin come from the adapter.
    role: MessageRole
    source_id: str
    seq: int
    text: str
    origin: MessageOrigin


class Excerpt(BaseModel):
    source_id: str
    text: str


class Summary(BaseModel):
    source_id: str = "summary"
    text: str
    refs: list[str]


class ProposedAction(BaseModel):
    tool: str
    arguments: dict


class History(BaseModel):
    complete: bool = False
    omitted_ranges: list[str] = Field(default_factory=list)
    collection_errors: list[str] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)


class ContextEnvelope(BaseModel):
    schema_version: str
    host: Host
    session: Session
    turn: Turn
    stage: Stage
    request: str
    messages: list[Message] = Field(default_factory=list)
    earlier_excerpts: list[Excerpt] = Field(default_factory=list)
    summary: Optional[Summary] = None
    proposed_action: Optional[ProposedAction] = None
    candidate_response: Optional[str] = None
    history: History = Field(default_factory=History)
    policy_version: str
    corpus_version: str
    language: str = "en"

    @field_validator("schema_version")
    @classmethod
    def _schema_version_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("schema_version must be a non-empty string")
        return v

    @model_validator(mode="after")
    def _check_stage_and_seq(self) -> "ContextEnvelope":
        problems: list[str] = []
        if self.stage == "pre_action" and self.proposed_action is None:
            problems.append("stage 'pre_action' requires proposed_action")
        if self.stage == "output" and self.candidate_response is None:
            problems.append("stage 'output' requires candidate_response")
        for i in range(1, len(self.messages)):
            if self.messages[i].seq <= self.messages[i - 1].seq:
                problems.append(
                    f"message seq must be unique and strictly ascending: "
                    f"seq {self.messages[i - 1].seq} at index {i - 1} is followed "
                    f"by seq {self.messages[i].seq} at index {i}"
                )
                break
        if problems:
            raise ValueError("; ".join(problems))
        return self


def validate_envelope(data: dict) -> ContextEnvelope:
    """Validate raw envelope data, raising EnvelopeError with clear messages."""
    try:
        return ContextEnvelope.model_validate(data)
    except ValidationError as e:
        errors = [
            f"{'.'.join(str(p) for p in err['loc']) or '(root)'}: {err['msg']}"
            for err in e.errors()
        ]
        raise EnvelopeError(
            f"invalid context envelope: {'; '.join(errors)}", errors=errors
        ) from e


def build_envelope(**kwargs) -> ContextEnvelope:
    """Small helper for tests: merge kwargs over a minimal valid envelope."""
    base = {
        "schema_version": "1",
        "host": {"name": "test-host", "version": "0", "mode": "test"},
        "session": {"id": "session-1"},
        "turn": {"id": "turn-1"},
        "stage": "input",
        "request": "",
        "messages": [],
        "earlier_excerpts": [],
        "history": {},
        "policy_version": "draft",
        "corpus_version": "draft",
        "language": "en",
    }
    return validate_envelope({**base, **kwargs})