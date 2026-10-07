"""PEA MCP server (plan M4): the four read-only review tools over stdio.

Every tool returns a pydantic model; the SDK derives the output schema
from the return annotation and sends it as ``structured_content``.

No tool accepts an approval, override, or release parameter — there is
no parameter the caller can pass to change a disposition. Reviews
opened by ``check_action`` on a ``review`` disposition go through
``runtime_store.open_review`` (agent-facing; resolve is an operator
process, not an MCP tool). Logging goes to stderr so stdout stays
protocol-clean for ``mcp.run(transport="stdio")``.

Importing this module has no side effects: construction is explicit
via :func:`create_server` (config: db path, policy path, interpreter
factory), and :func:`main` runs the stdio loop.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from . import assess, corpus as corpus_mod, policy as policy_mod
from .context import EnvelopeError, validate_envelope

# Default paths resolve against the repo root (src/patristic_ethics/..) so
# the server works from any cwd; tests pass explicit paths instead.
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = _REPO_ROOT / "corpus" / "units.db"
DEFAULT_POLICY_PATH = _REPO_ROOT / "policy" / "rules.json"
DEFAULT_RUNTIME_DB_PATH = _REPO_ROOT / "corpus" / "runtime.db"

_MISSING_CLAUSE = "insufficient evidence in this collection"


class CitationOut(BaseModel):
    """One verified-provenance citation."""

    unit_id: str
    author: str
    work: str
    locus: str | None = None
    quote: str
    language: str
    rights_status: str


class CheckActionResult(BaseModel):
    """check_action result: the assessment decision plus guidance.

    ``action`` is PEA's recommendation; the host adapter still owns the
    enforcement hook. No field here approves or overrides anything.
    A malformed envelope yields action="withhold" plus ``error``.
    """

    action: Literal["proceed", "guide", "refuse", "clarify", "review", "withhold"]
    disposition: Literal["allow", "guide", "refuse", "clarify", "review"] | None = None
    principle_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    source_status: Literal["verified", "partial", "missing"] = "verified"
    urgent_care: bool = False
    non_overridable: bool = False
    guidance_text: str = ""
    citations: list[CitationOut] = Field(default_factory=list)
    review_id: str | None = None
    review_note: str | None = None
    context_limited: bool = False
    error: str | None = None


class UnitOut(BaseModel):
    """A corpus unit as exposed by search_corpus."""

    id: str
    author: str
    work: str
    locus: str | None = None
    language: str
    text: str | None = None
    rights_status: str
    source_url: str


class SearchResult(BaseModel):
    query: str
    units: list[UnitOut] = Field(default_factory=list)
    source_status: Literal["verified", "partial", "missing"] = "verified"


class PassageResult(BaseModel):
    """get_passage result; unit is null on an unknown id (expected miss)."""

    unit: UnitOut | None = None
    found: bool = True
    error: str | None = None


class CitationResult(BaseModel):
    """cite_father result: only citations whose quote verifies exactly."""

    topic: str
    citations: list[CitationOut] = Field(default_factory=list)
    source_status: Literal["verified", "partial", "missing"] = "missing"
    text: str = ""


def _default_interpreter_factory() -> Any:
    from .interpreter import OllamaInterpreter

    return OllamaInterpreter()


def _fts_quote(query: str) -> str:
    """One FTS5 phrase term, quoted; raw user text never reaches MATCH."""
    return '"' + query.replace('"', '""') + '"'


def _citation_out(unit: Any) -> CitationOut:
    return CitationOut(
        unit_id=unit.id,
        author=unit.author,
        work=unit.work,
        locus=unit.locus,
        quote=unit.text or "",
        language=unit.language,
        rights_status=unit.rights_status,
    )


def _unit_out(unit: Any) -> UnitOut:
    return UnitOut(
        id=unit.id,
        author=unit.author,
        work=unit.work,
        locus=unit.locus,
        language=unit.language,
        text=unit.text,
        rights_status=unit.rights_status,
        source_url=unit.source_url,
    )


def _log(msg: str) -> None:
    # stderr only: stdout carries the stdio JSON-RPC protocol.
    print(msg, file=sys.stderr, flush=True)


def create_server(
    db_path: str | Path = DEFAULT_DB_PATH,
    policy_path: str | Path = DEFAULT_POLICY_PATH,
    interpreter_factory: Callable[[], Any] = _default_interpreter_factory,
    runtime_db_path: str | Path | None = DEFAULT_RUNTIME_DB_PATH,
    corpus_version: str = "0.1.0-draft",
) -> Any:
    """Build a configured MCPServer with the four PEA tools registered."""
    from mcp.server import MCPServer

    db_path = Path(db_path)
    policy_doc = policy_mod.load_policy(policy_path)
    interpreter = interpreter_factory()

    def _open_review(session_id: str, result: Any, envelope: Any) -> tuple[str | None, str | None]:
        """Open a review for a reviewable decision; None + note on refusal."""
        if result.action != "review" or result.decision is None:
            return None, None
        # ponytail: lazy import; runtime_store exists (M3) but a missing
        # module must degrade to review_id=None, never a crash.
        try:
            from . import runtime_store
        except ImportError:
            return None, "review store unavailable; no review opened"
        store = runtime_store.RuntimeStore(runtime_db_path)
        try:
            review_id = store.open_review(
                session_id,
                {"action": result.action, "reason": result.decision.reason},
                {"envelope": json.loads(envelope.model_dump_json())},
                policy_doc.get("policy_version", ""),
                non_overridable=bool(result.decision.non_overridable),
            )
            return review_id, None
        except runtime_store.ReviewNotAllowed:
            # A non-overridable decision can never open a review.
            return None, "decision is non-overridable; no review can be opened"
        finally:
            store.conn.close()

    def _context_limited(envelope: Any) -> bool:
        """history.complete is False AND nothing beyond the request exists."""
        if envelope.history.complete:
            return False
        return not envelope.messages and not envelope.earlier_excerpts

    server = MCPServer("pea")

    @server.tool()
    def check_action(envelope_json: str) -> CheckActionResult:
        """Assess one conversation turn and recommend an action.

        envelope_json is a ContextEnvelope JSON document. Returns the
        recommended action, the matched principles, composed guidance,
        and verified citations. There is no approval or override
        parameter: the decision is never caller-overrideable here.
        A malformed envelope yields action="withhold" plus ``error``.
        """
        try:
            data = json.loads(envelope_json)
        except json.JSONDecodeError as e:
            _log(f"PEA_INVALID_ENVELOPE: not valid JSON: {e}")
            return CheckActionResult(
                action="withhold", error=f"PEA_INVALID_ENVELOPE: not valid JSON: {e}"
            )
        try:
            envelope = validate_envelope(data)
        except EnvelopeError as e:
            _log(f"PEA_INVALID_ENVELOPE: {e}")
            return CheckActionResult(action="withhold", error=str(e))

        result = assess.assess(
            envelope,
            interpreter=interpreter,
            policy_doc=policy_doc,
            db_path=db_path,
            corpus_version=corpus_version,
        )
        decision = result.decision
        guidance_result = result.guidance

        citations: list[CitationOut] = []
        guidance_text = ""
        source_status = "missing"
        if guidance_result is not None:
            guidance_text = guidance_result.text
            source_status = guidance_result.source_status
            citations = [
                CitationOut(
                    unit_id=c.unit_id,
                    author=c.author,
                    work=c.work,
                    locus=c.locus,
                    quote=c.quote,
                    language=c.language,
                    rights_status=c.rights_status,
                )
                for c in guidance_result.citations
            ]

        review_id, review_note = _open_review(envelope.session.id, result, envelope)

        return CheckActionResult(
            action=result.action,
            disposition=decision.disposition if decision is not None else None,
            principle_ids=list(decision.principle_ids) if decision is not None else [],
            reason=decision.reason if decision is not None else (result.failure.reason if result.failure else ""),
            source_status=source_status,
            urgent_care=bool(decision.urgent_care) if decision is not None else False,
            non_overridable=bool(decision.non_overridable) if decision is not None else False,
            guidance_text=guidance_text,
            citations=citations,
            review_id=review_id,
            review_note=review_note,
            context_limited=_context_limited(envelope),
        )

    @server.tool()
    def search_corpus(query: str, limit: int = 5) -> SearchResult:
        """FTS5 search over the patristic corpus (text, author, work)."""
        if limit < 1:
            limit = 1
        try:
            units = corpus_mod.search_passages(db_path, _fts_quote(query), limit=limit)
        except Exception as e:  # missing file or FTS error: a fact, not a verdict
            _log(f"PEA_CORPUS_UNAVAILABLE: {e}")
            return SearchResult(query=query, units=[], source_status="missing")
        units_out = [_unit_out(u) for u in units]
        return SearchResult(
            query=query,
            units=units_out,
            source_status="verified" if units_out else "missing",
        )

    @server.tool()
    def get_passage(unit_id: str) -> PassageResult:
        """Fetch one full corpus unit by id; unit is null on unknown id."""
        try:
            unit = corpus_mod.get_passage(db_path, unit_id)
        except Exception as e:
            _log(f"PEA_CORPUS_UNAVAILABLE: {e}")
            return PassageResult(found=False, error=f"PEA_CORPUS_UNAVAILABLE: {e}")
        if unit is None:
            # Expected miss: an explicit error field, not a raise — v2
            # sanitizes unexpected exceptions to an opaque -32603.
            return PassageResult(
                found=False,
                error=f"PEA_UNKNOWN_UNIT: no corpus unit with id {unit_id!r}",
            )
        return PassageResult(unit=_unit_out(unit), found=True)

    @server.tool()
    def cite_father(topic: str, limit: int = 3) -> CitationResult:
        """Find and verify patristic citations for a topic.

        Returns only citations whose quote verifies exactly against the
        stored text; when nothing verifies, source_status is "missing"
        and the text says so — never a fabricated citation.
        """
        if limit < 1:
            limit = 1
        try:
            units = corpus_mod.search_passages(db_path, _fts_quote(topic), limit=limit)
        except Exception as e:
            _log(f"PEA_CORPUS_UNAVAILABLE: {e}")
            units = []
        citations = [
            _citation_out(u)
            for u in units
            if u.text and corpus_mod.verify_quote(db_path, u.id, u.text)
        ]
        if citations:
            return CitationResult(
                topic=topic,
                citations=citations,
                source_status="verified",
                text="",
            )
        return CitationResult(
            topic=topic,
            citations=[],
            source_status="missing",
            text=_MISSING_CLAUSE,
        )

    return server


def main() -> None:
    """Run the PEA MCP server over stdio (stdout stays protocol-clean)."""
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()