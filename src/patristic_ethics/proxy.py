"""PEA double-ended MCP proxy (plan §M3 items 2 and 4).

Wraps a real MCP server: the host sees the downstream server's tools
with the same names/descriptions/schemas, but every ``tools/call`` is
assessed pre-action and blocked calls never reach the downstream
process.

IMPLEMENTED (all tested in tests/integration/test_proxy.py):

- Gating core :func:`assess_tool_call` — stdlib-only, no SDK import.
  Builds a ``pre_action`` ContextEnvelope from the tool name and
  arguments, runs the injected assessor, and maps the action:
  proceed/guide -> forward; refuse/clarify/review/withhold -> block.
  ``context_limited`` is always True from this core: the proxy has no
  host conversation history, so every assessment is arguments-only
  (``history.complete=False`` plus the collection error
  "arguments-only assessment").
- Blocked-error surface: the host receives a ``CallToolResult`` with
  ``is_error=True`` whose text is :func:`build_block_error` of the
  payload ``{"status": "blocked", "pea_action": ..., "reason": ...,
  "principle_ids": [...], "review_id": ...}``. Raising ``ToolError``
  at the lowlevel layer surfaces as a protocol error instead, and the
  SDK sanitizes generic exceptions to an opaque internal error — the
  is_error result is the model-visible surface, chosen deliberately
  (probe-verified against the pinned mcp 2.3 SDK).
- Review disposition: opens a pending review via ``open_review_fn``
  (wire it to ``runtime_store.RuntimeStore.open_review``; called with
  ``non_overridable`` as a keyword) and rides ``review_id`` in the
  blocked payload. Refuse short-circuits before review and never
  opens one, so ``ReviewNotAllowed`` cannot fire on this path.
- Audit: one ``try_record_event`` per call with a deterministic
  event_id = sha256 over canonical {session, tool, arguments};
  INSERT OR IGNORE makes retried calls idempotent at the db level.
  Audit failures are swallowed: a broken audit store must not change
  the gating decision.
- Allowlist: None (default) = every tool gated. A set = tools in the
  set gated; uncovered tools forward unchanged (passthrough), the
  event recorded with action/disposition "passthrough". Documented
  choice: an uncovered tool is not silently dropped, and gating it
  against a policy never written for it would be theater.
- Recursion guard :func:`is_recursive_target`: refuses a downstream
  command mentioning ``patristic_ethics`` (PEA-in-PEA). Ceiling:
  name-based; a renamed PEA clone is not caught.
- Wiring :func:`create_proxy_server` + :func:`main`: host side is a
  lowlevel ``mcp.server.lowlevel.Server`` served over stdio;
  downstream is an ``mcp.Client`` over a spawned stdio subprocess.
  tools/list and tools/call pass through; schemas and results are
  forwarded unchanged. The gate (blocking interpreter call) runs on a
  worker thread so a slow local model cannot stall the event loop.

DELIBERATE V1 GAPS (documented, not hidden):

- Guidance injection is NOT done: a ``guide`` action forwards pure;
  the guidance text lives in the audit record only. Appending a
  pea_note block to proxied results would alter downstream output.
- Tools only: resources, prompts, and sampling are not proxied.
- tools/list passes through dynamically, but downstream
  list-changed notifications are not subscribed.
- The blocked payload is data for the calling model; it grants no
  approval or override path.
- stdout carries the MCP protocol only; diagnostics go to stderr.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from . import policy as policy_mod
from .context import validate_envelope

_FORWARD_ACTIONS = {"proceed", "guide"}


@dataclass
class ProxyDecision:
    """Gating verdict for one proxied tool call.

    forward: True -> call the downstream tool. False -> do not; the
    host sees the structured payload as an is_error result.
    payload: the blocked-error payload (None when forwarding).
    context_limited: always True here (arguments-only assessment).
    review_id: set when a review disposition opened a pending review.
    """

    forward: bool
    payload: dict | None = None
    context_limited: bool = True
    review_id: str | None = None
    dispatch_review_id: str | None = None


def _event_id(session_id: str, name: str, args: dict) -> str:
    """Deterministic id so retried hook calls do not duplicate audit rows."""
    canonical = json.dumps(
        {"session_id": session_id, "tool": name, "arguments": args},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record(store: Any, event_id: str, session_id: str, action: str,
            disposition: str, principle_ids: list[str], audit: dict) -> None:
    if store is None:
        return
    try:
        store.try_record_event(
            event_id, session_id, "pre_action", action, disposition,
            principle_ids,
            audit.get("policy_version", ""), audit.get("corpus_version", ""),
            audit.get("latency_ms"),
        )
    except Exception:  # audit is observability; it must not change gating
        print("PEA_PROXY_AUDIT_FAILED", file=sys.stderr, flush=True)


def assess_tool_call(
    name: str,
    args: dict | None,
    *,
    assess_fn: Callable[[Any], Any],
    open_review_fn: Callable[..., str] | None = None,
    runtime_store: Any = None,
    claim_approval_fn: Callable[..., str | None] | None = None,
    session_id: str = "proxy",
    allowlist: set[str] | None = None,
) -> ProxyDecision:
    """Gate one tool call before forwarding (plan §M3 item 4).

    Allowlist semantics: allowlist=None gates every tool; a set gates
    the covered tools and forwards uncovered tools unchanged
    (passthrough, audited as "passthrough"). This function never has
    host history, so context_limited is always True.

    assess_fn takes a validated ContextEnvelope and returns an
    ``assess.AssessResult``. open_review_fn must accept
    ``(session_id, action, context, policy_version, non_overridable=False)``
    and return a review_id (runtime_store.RuntimeStore.open_review fits).
    An assess_fn crash fails closed as a withhold, never a silent forward.
    """
    args = args or {}
    eid = _event_id(session_id, name, args)

    if allowlist is not None and name not in allowlist:
        _record(runtime_store, eid, session_id, "passthrough", "passthrough",
                [], {})
        return ProxyDecision(forward=True, payload=None, context_limited=True)

    envelope = validate_envelope({
        "schema_version": "1",
        "host": {"name": "pea-proxy", "version": "0.1.0", "mode": "native"},
        "session": {"id": session_id},
        "turn": {"id": "proxy-" + eid[:16]},
        "stage": "pre_action",
        # Keep the proposed operation in the evidence-bearing request too;
        # native hosts may separately provide the current user objective.
        "request": f"Tool call: {name}\nArguments: {json.dumps(args, sort_keys=True)}",
        "messages": [],
        "earlier_excerpts": [],
        "proposed_action": {"tool": name, "arguments": args},
        "history": {"complete": False, "collection_errors": ["arguments-only assessment"]},
        "policy_version": "0.1.0",
        "corpus_version": "0.1.0-draft",
        "language": "en",
    })

    try:
        result = assess_fn(envelope)
    except Exception as e:  # fail closed: operational failure != forward
        _record(runtime_store, eid, session_id, "withhold", "withhold",
                [], {})
        return ProxyDecision(
            forward=False,
            payload={
                "status": "blocked",
                "pea_action": "withhold",
                "reason": f"assessment failed: {e}",
                "principle_ids": [],
                "review_id": None,
            },
        )

    action = result.action
    decision = result.decision
    principle_ids = list(decision.principle_ids) if decision is not None else []
    reason = (
        (result.guidance.text if result.guidance is not None else "")
        or (result.failure.reason if result.failure is not None else "")
        or action
    )
    audit = result.audit

    if action in _FORWARD_ACTIONS:
        # guide forwards pure: guidance is recorded in the audit only
        # (deliberate v1 gap, see module docstring).
        _record(runtime_store, eid, session_id, action,
                decision.disposition if decision is not None else action,
                principle_ids, audit)
        return ProxyDecision(forward=True, payload=None, context_limited=True)

    review_id = None
    # Bind human review to the exact proposed tool operation. Host dialogue
    # is unavailable on this MCP proxy path and is explicitly marked limited.
    reviewed_action = {"tool": name, "arguments": args}
    reviewed_context = {"session_id": session_id, "context_limited": True}
    policy_version = audit.get("policy_version", "")
    if action == "review" and open_review_fn is not None:
        if claim_approval_fn is not None:
            try:
                claimed = claim_approval_fn(
                    session_id, reviewed_action, reviewed_context, policy_version
                )
            except Exception:
                claimed = None
            if claimed:
                _record(runtime_store, eid, session_id, action,
                        decision.disposition if decision is not None else action,
                        principle_ids, audit)
                return ProxyDecision(
                    forward=True, payload=None, context_limited=True,
                    dispatch_review_id=claimed,
                )
        try:
            review_id = open_review_fn(
                session_id,
                reviewed_action,
                reviewed_context,
                policy_version,
                non_overridable=False,  # review dispositions are never refuse
                reason=reason,
            )
        except Exception as e:
            review_id = None
            reason = f"{reason} (review could not be opened: {e})"

    payload = {
        "status": "blocked",
        "pea_action": action,
        "reason": reason,
        "principle_ids": principle_ids,
        "review_id": review_id,
    }
    _record(runtime_store, eid, session_id, action,
            decision.disposition if decision is not None else action,
            principle_ids, audit)
    return ProxyDecision(
        forward=False, payload=payload, context_limited=True, review_id=review_id
    )


def build_block_error(payload: dict) -> str:
    """JSON text for the blocked-error surface (host-visible payload)."""
    return json.dumps(payload, sort_keys=True)


def is_recursive_target(command: list[str] | str) -> bool:
    """True when the downstream command mentions patristic_ethics.

    PEA-in-PEA guard. Ceiling: name-based; a renamed clone is not caught.
    """
    tokens = shlex.split(command) if isinstance(command, str) else list(command)
    return any("patristic_ethics" in t for t in tokens)


def create_proxy_server(
    downstream: Any,
    gate: Callable[[str, dict], ProxyDecision],
    mark_dispatched_fn: Callable[[str], bool] | None = None,
) -> Any:
    """Host-facing lowlevel MCP Server over an entered downstream Client.

    tools/list and tools/call pass through unchanged; the gate runs
    before every forward. Blocked calls return an is_error CallToolResult
    carrying the JSON payload as text (the model-visible surface; see
    module docstring). SDK imports are lazy so the gating core stays
    SDK-free.
    """
    from mcp.server.lowlevel import Server
    import mcp.types as types
    import anyio

    async def on_list_tools(ctx, params):
        cursor = params.cursor if params is not None else None
        return await downstream.list_tools(cursor=cursor)

    async def on_call_tool(ctx, params):
        args = params.arguments or {}
        try:
            decision = await anyio.to_thread.run_sync(
            lambda: gate(params.name, args)
            )
        except Exception as e:  # fail closed even if the gate itself crashes
            decision = ProxyDecision(
                forward=False,
                payload={
                    "status": "blocked",
                    "pea_action": "withhold",
                    "reason": f"gate failed: {e}",
                    "principle_ids": [],
                    "review_id": None,
                },
            )
        if not decision.forward:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=build_block_error(decision.payload or {}),
                    )
                ],
                is_error=True,
            )
        result = await downstream.call_tool(params.name, args)
        if decision.dispatch_review_id and mark_dispatched_fn is not None:
            mark_dispatched_fn(decision.dispatch_review_id)
        return result

    return Server("pea-proxy", on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def _serve(cmd: list[str], gate, mark_dispatched_fn=None) -> None:
    """Spawn the downstream stdio server and serve the proxy over stdio."""
    from mcp import Client, StdioServerParameters
    from mcp.server.stdio import stdio_server

    params = StdioServerParameters(command=cmd[0], args=cmd[1:])
    async with Client(params) as downstream:
        server = create_proxy_server(downstream, gate, mark_dispatched_fn)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )


def main(argv: list[str] | None = None) -> None:
    """Run the PEA proxy over stdio (stdout is protocol; stderr is diagnostics)."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="patristic-ethics-proxy",
        description="PEA pre-action gating proxy in front of a downstream MCP server.",
    )
    parser.add_argument(
        "--downstream-cmd", required=True,
        help='downstream server command, shell-split, e.g. "mcp-server-filesystem /tmp"',
    )
    parser.add_argument("--backend", choices=["fake", "ollama"], default="fake",
                        help="interpreter backend (default: fake, for plumbing tests)")
    parser.add_argument("--db", default=None, help="corpus db path")
    parser.add_argument("--policy", default=None, help="policy rules.json path")
    parser.add_argument("--runtime-db", default=None, help="runtime review/audit db path")
    parser.add_argument(
        "--allowlist", default=None,
        help="comma-separated gated tool names; tools outside the set pass through "
             "ungated (audited as passthrough); omit to gate every tool",
    )
    a = parser.parse_args(argv)

    cmd = shlex.split(a.downstream_cmd)
    if not cmd:
        parser.error("--downstream-cmd is empty")
    if is_recursive_target(cmd):
        print(
            "PEA_PROXY_REFUSED: downstream command looks like PEA itself "
            "(PEA-in-PEA recursion guard)",
            file=sys.stderr,
        )
        raise SystemExit(2)

    from . import assess as assess_mod
    from . import runtime_store as runtime_store_mod
    from .interpreter import FakeInterpreter, OllamaInterpreter
    from .mcp_server import (
        DEFAULT_DB_PATH, DEFAULT_POLICY_PATH, DEFAULT_RUNTIME_DB_PATH,
    )

    db_path = a.db or DEFAULT_DB_PATH
    policy_doc = policy_mod.load_policy(a.policy or DEFAULT_POLICY_PATH)
    interpreter = FakeInterpreter({}) if a.backend == "fake" else OllamaInterpreter()
    store = runtime_store_mod.RuntimeStore(a.runtime_db or DEFAULT_RUNTIME_DB_PATH)
    allowlist = (
        set(filter(None, a.allowlist.split(",")))
        if a.allowlist is not None else None
    )
    # stdio has no transport session id; scope approvals to this proxy
    # process so a restart or another agent session cannot reuse them.
    proxy_session_id = uuid.uuid4().hex

    def assess_fn(envelope):
        return assess_mod.assess(
            envelope, interpreter=interpreter, policy_doc=policy_doc, db_path=db_path
        )

    def gate(name: str, args: dict) -> ProxyDecision:
        return assess_tool_call(
            name, args,
            assess_fn=assess_fn,
            open_review_fn=store.open_review,
            runtime_store=store,
            claim_approval_fn=store.claim_matching_approval,
            session_id=proxy_session_id,
            allowlist=allowlist,
        )

    import anyio

    anyio.run(_serve, cmd, gate, store.mark_dispatched)


if __name__ == "__main__":
    main()
