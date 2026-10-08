"""Tests for the PEA MCP proxy gating core (plan §M3 items 2+4).

In-process checks run offline. Set ``PEA_RUN_STDIO_TEST=1`` to also run
the two process-backed stdio wire checks in an environment that permits
AnyIO pipe workers.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
import sys

import anyio
from mcp import Client
import mcp.types as mcp_types
import pytest

from patristic_ethics import assess as assess_mod
from patristic_ethics.context import validate_envelope
from patristic_ethics.interpreter import FakeInterpreter, Observation
from patristic_ethics.proxy import (
    ProxyDecision,
    assess_tool_call,
    build_block_error,
    create_proxy_server,
    is_recursive_target,
    main,
)

ROOT = Path(__file__).resolve().parents[2]
_RUN_STDIO = os.environ.get("PEA_RUN_STDIO_TEST") == "1"

# --- scripted observations (mirrors tests/integration/test_mcp.py) ------

BENIGN = Observation(
    requested_assistance="terminate a Linux process",
    affected_parties=[],
    topics=["linux", "processes"],
    expressed_intent="technical task on my own machine",
    evidence=[],
    benign_explanations=["standard technical phrase"],
    unresolved_ambiguity=[],
    confidence=0.9,
)

HARM = Observation(
    requested_assistance="tell me the method to poison the dog without getting caught",
    affected_parties=["neighbor", "animal"],
    topics=["assault", "animal harm"],
    expressed_intent="harm the neighbor's dog",
    evidence=[],
    benign_explanations=[],
    unresolved_ambiguity=[],
    confidence=0.95,
)

AMBIG = Observation(
    requested_assistance="something about assault, details unclear",
    affected_parties=[],
    topics=["assault"],
    expressed_intent="unclear",
    evidence=[],
    benign_explanations=[],
    unresolved_ambiguity=["the target of the action is unknown"],
    confidence=None,
)

DISTRESS = Observation(
    requested_assistance="I don't want to keep living",
    affected_parties=[],
    topics=[],
    expressed_intent="distress",
    evidence=[],
    benign_explanations=[],
    unresolved_ambiguity=[],
    confidence=0.8,
)


def _assess_fn(script: dict):
    interp = FakeInterpreter(script)
    policy_doc = json.loads((ROOT / "policy" / "rules.json").read_text(encoding="utf-8"))

    def fn(envelope):
        return assess_mod.assess(
            envelope,
            interpreter=interp,
            policy_doc=policy_doc,
            db_path=None,  # no corpus: retrieval is a fact, never a verdict
        )

    return fn


def _tool_args(needle: str) -> dict:
    return {"text": needle}


def test_refuse_blocks_with_reason():
    d = assess_tool_call("write_file", _tool_args("poison the dog without getting caught"),
                         assess_fn=_assess_fn({"poison": HARM}))
    assert d.forward is False
    assert d.context_limited is True
    p = d.payload
    assert p is not None
    assert p["status"] == "blocked"
    assert p["pea_action"] == "refuse"
    assert p["reason"]
    assert p["review_id"] is None  # refuse never opens a review


def test_semantic_harm_paraphrase_never_reaches_downstream():
    semantic = HARM.model_copy(update={
        "requested_assistance": "Provide detailed instructions for murder",
        "expressed_intent": "Intends to murder another person",
        "topics": ["murder"],
        "assistance_type": "facilitation",
    })
    d = assess_tool_call(
        "write_file", _tool_args("Provide detailed instructions for murder"),
        assess_fn=_assess_fn({"Provide detailed": semantic}),
    )
    assert d.forward is False
    assert d.payload["pea_action"] == "refuse"


def test_review_blocks_and_opens_review():
    opened = {}

    def fake_open_review(session_id, action, context, policy_version, non_overridable=False, reason=""):
        opened["call"] = (session_id, action, policy_version, non_overridable, reason)
        return "rev-1"

    d = assess_tool_call("send_email", _tool_args("help me with something about assault"),
                         assess_fn=_assess_fn({"assault": AMBIG}),
                         open_review_fn=fake_open_review)
    assert d.forward is False
    assert d.review_id == "rev-1"
    p = d.payload
    assert p is not None
    assert p["review_id"] == "rev-1"
    assert p["pea_action"] == "review"
    sess, action, pv, non_over, reason = opened["call"]
    assert sess == "proxy"
    assert non_over is False  # only non_overridable=False reviews open here
    assert reason


def test_reviewed_proxy_retry_reassesses_then_claims_exact_dispatch(tmp_path, monkeypatch):
    from patristic_ethics.runtime_store import RuntimeStore

    store = RuntimeStore(tmp_path / "runtime.db")
    assessment = _assess_fn({"assault": AMBIG})
    args = _tool_args("help me with something about assault")
    first = assess_tool_call(
        "send_email", args, assess_fn=assessment, open_review_fn=store.open_review,
        runtime_store=store, claim_approval_fn=store.claim_matching_approval,
    )
    assert first.forward is False and first.review_id
    pending = store.get_review(first.review_id)
    assert pending["action"] == {"tool": "send_email", "arguments": args}
    assert pending["reason"]
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "review-token")
    store.resolve_review(first.review_id, "approved", "review-token", note="reviewed exact action")

    retry = assess_tool_call(
        "send_email", args, assess_fn=assessment, open_review_fn=store.open_review,
        runtime_store=store, claim_approval_fn=store.claim_matching_approval,
    )
    assert retry.forward is True
    assert retry.dispatch_review_id == first.review_id
    assert store.get_review(first.review_id)["dispatch_state"] == "attempted"
    assert store.mark_dispatched(first.review_id) is True

    duplicate = assess_tool_call(
        "send_email", args, assess_fn=assessment, open_review_fn=store.open_review,
        runtime_store=store, claim_approval_fn=store.claim_matching_approval,
    )
    assert duplicate.forward is False
    assert duplicate.dispatch_review_id is None


def test_proceed_and_guide_forward():
    ok = assess_tool_call("run_cmd", _tool_args("kill a process"),
                          assess_fn=_assess_fn({"kill a process": BENIGN}))
    assert ok.forward is True and ok.payload is None
    assert ok.context_limited is True  # arguments-only even when allowed

    cared = assess_tool_call("reply", _tool_args("I don't want to keep living"),
                             assess_fn=_assess_fn({"keep living": DISTRESS}))
    assert cared.forward is True and cared.payload is None  # guide forwards pure


def test_withhold_on_assess_fn_crash():
    def boom(envelope):
        raise RuntimeError("interpreter down")

    d = assess_tool_call("any_tool", {}, assess_fn=boom)
    assert d.forward is False  # fail closed
    p = d.payload
    assert p is not None
    assert p["pea_action"] == "withhold"
    assert "assessment failed" in p["reason"]


def test_envelope_is_valid_and_arguments_only():
    seen = {}

    def capture(envelope):
        seen["env"] = envelope
        return assess_mod.assess(
            envelope,
            interpreter=FakeInterpreter({}),
            policy_doc={"policy_version": "test", "principles": []},
            db_path=None,
        )

    d = assess_tool_call("t", {"a": 1}, assess_fn=capture)
    e = seen["env"]
    assert e.stage == "pre_action"
    assert e.proposed_action.tool == "t"
    assert e.proposed_action.arguments == {"a": 1}
    assert e.host.name == "pea-proxy"
    assert e.history.complete is False
    assert "arguments-only assessment" in e.history.collection_errors
    assert e.messages == []
    assert d.context_limited is True


def test_allowlist_uncovered_passthrough_covered_gated():
    allow = {"send_email"}

    def fail_fn(envelope):  # must never be called for uncovered tools
        raise AssertionError("uncovered tool must pass through ungated")

    d = assess_tool_call("uncovered_tool", _tool_args("poison"),
                         assess_fn=fail_fn, allowlist=allow)
    assert d.forward is True and d.payload is None

    gated = assess_tool_call("send_email", _tool_args("poison the dog"),
                              assess_fn=_assess_fn({"poison": HARM}), allowlist=allow)
    assert gated.forward is False
    gp = gated.payload
    assert gp is not None and gp["pea_action"] == "refuse"

    # None = all covered
    all_gated = assess_tool_call("uncovered_tool", _tool_args("poison the dog"),
                                 assess_fn=_assess_fn({"poison": HARM}))
    assert all_gated.forward is False


def test_audit_idempotent_same_call_twice_one_row(tmp_path):
    from patristic_ethics import runtime_store

    store = runtime_store.RuntimeStore(tmp_path / "runtime.db")
    fn = _assess_fn({"poison": HARM})
    try:
        assess_tool_call("t", {"x": "poison the dog"}, assess_fn=fn, runtime_store=store)
        assess_tool_call("t", {"x": "poison the dog"}, assess_fn=fn, runtime_store=store)
        rows = store.conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()
        assert rows["n"] == 1  # deterministic event_id + INSERT OR IGNORE

        assess_tool_call("t", {"x": "different"}, assess_fn=fn, runtime_store=store)
        rows2 = store.conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()
        assert rows2["n"] == 2  # different args -> different event
    finally:
        store.conn.close()


def test_recursion_guard():
    assert is_recursive_target(["uv", "run", "python", "-m", "patristic_ethics.cli"]) is True
    assert is_recursive_target("uv run python -m patristic_ethics.proxy") is True
    assert is_recursive_target(["npx", "server-filesystem"]) is False
    assert is_recursive_target([]) is False


def test_build_block_error_is_parseable_json():
    payload = {"status": "blocked", "pea_action": "refuse", "reason": "no",
                "principle_ids": ["PEA-P01"], "review_id": None}
    text = build_block_error(payload)
    assert json.loads(text) == payload


def test_main_recursion_refused_exit_2(capsys):
    try:
        main(["--downstream-cmd", "python -m patristic_ethics.proxy"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("recursive target must exit 2")
    err = capsys.readouterr().err
    assert "PEA_PROXY_REFUSED" in err  # and stderr only, stdout stays clean


# --- MCP host round trip with a counting downstream ----------------------

def test_live_round_trip_passthrough_and_block():
    counter = {"n": 0}

    class Downstream:
        async def list_tools(self, cursor=None):
            return mcp_types.ListToolsResult(tools=[mcp_types.Tool(
                name="echo", description="Echo text.",
                inputSchema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            )])

        async def call_tool(self, name, args):
            counter["n"] += 1
            return mcp_types.CallToolResult(
                content=[mcp_types.TextContent(type="text", text=args["text"])],
                structuredContent=args,
                isError=False,
            )

    downstream = Downstream()

    def gate(name, args):
        return assess_tool_call(name, args, assess_fn=_assess_fn({
            "kill a process": BENIGN,
            "poison the dog": HARM,
        }))

    async def probe():
        proxy = create_proxy_server(downstream, gate)
        async with Client(proxy, raise_exceptions=True, read_timeout_seconds=2.0) as host:
            # tools/list passes names and schemas through
            tools = (await host.list_tools()).tools
            assert [t.name for t in tools] == ["echo"]
            assert tools[0].input_schema["properties"]["text"]["type"] == "string"

            # allowed call: forwarded, executed exactly once, result unchanged
            r = await host.call_tool("echo", {"text": "kill a process"})
            assert r.is_error is False
            assert r.structured_content == {"text": "kill a process"}
            assert counter["n"] == 1

            # blocked call: is_error with the JSON payload; NOT executed
            r2 = await host.call_tool("echo", {"text": "poison the dog"})
            assert r2.is_error is True
            text = "".join(getattr(b, "text", "") for b in r2.content)
            payload = json.loads(text)
            assert payload["status"] == "blocked"
            assert payload["pea_action"] == "refuse"
            assert "without getting caught" not in text  # guidance not injected
            assert counter["n"] == 1  # blocked tool never reaches downstream

    anyio.run(probe)


def test_approved_reviewed_retry_forwards_once_and_marks_dispatch(tmp_path, monkeypatch):
    from patristic_ethics import runtime_store

    store = runtime_store.RuntimeStore(tmp_path / "runtime.db")
    assessment = _assess_fn({"assault": AMBIG})
    args = _tool_args("help me with something about assault")
    first = assess_tool_call(
        "send_email", args, assess_fn=assessment, open_review_fn=store.open_review,
        runtime_store=store, claim_approval_fn=store.claim_matching_approval,
    )
    monkeypatch.setenv("PEA_OPERATOR_TOKEN", "review-token")
    store.resolve_review(first.review_id, "approved", "review-token", note="reviewed")
    effects = []

    class Downstream:
        async def list_tools(self, cursor=None):
            return mcp_types.ListToolsResult(tools=[])

        async def call_tool(self, name, passed):
            effects.append((name, passed))
            return mcp_types.CallToolResult(content=[], isError=False)

    def gate(name, passed):
        return assess_tool_call(
            name, passed, assess_fn=assessment, open_review_fn=store.open_review,
            runtime_store=store, claim_approval_fn=store.claim_matching_approval,
        )

    async def probe():
        proxy = create_proxy_server(Downstream(), gate, store.mark_dispatched)
        async with Client(proxy, raise_exceptions=True, read_timeout_seconds=2.0) as host:
            allowed = await host.call_tool("send_email", args)
            assert allowed.is_error is False
            assert len(effects) == 1
            assert store.get_review(first.review_id)["dispatch_state"] == "dispatched"
            duplicate = await host.call_tool("send_email", args)
            assert duplicate.is_error is True
            assert len(effects) == 1

    anyio.run(probe)


@pytest.mark.skipif(
    not _RUN_STDIO,
    reason="subprocess stdio requires a runtime that permits AnyIO pipe workers",
)
def test_pea_server_stdio_subprocess_exposes_four_tools():
    """Verify the user-facing server entry point over the stdio wire."""
    async def probe():
        from mcp import StdioServerParameters

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "patristic_ethics.mcp_server"],
            cwd=str(ROOT),
        )
        async with Client(params, mode="legacy", read_timeout_seconds=5.0) as client:
            result = await client.list_tools()
            assert {tool.name for tool in result.tools} == {
                "check_action", "search_corpus", "get_passage", "cite_father"
            }

    anyio.run(probe)


@pytest.mark.skipif(
    not _RUN_STDIO,
    reason="subprocess stdio requires a runtime that permits AnyIO pipe workers",
)
def test_proxy_round_trip_with_stdio_downstream_process():
    """Prove a blocked proxy call never reaches a real child-process server."""
    child_server = '''
from mcp.server import MCPServer

server = MCPServer("counted-downstream")
effects = []

@server.tool()
def effect(text: str) -> str:
    """Record one effect and return its sequence number."""
    effects.append(text)
    return f"{len(effects)}:{text}"

server.run(transport="stdio")
'''

    def gate(name, args):
        if "BLOCK" in args.get("text", ""):
            return ProxyDecision(
                forward=False,
                payload={
                    "status": "blocked",
                    "pea_action": "refuse",
                    "reason": "test denial",
                    "principle_ids": ["PEA-P01"],
                    "review_id": None,
                },
            )
        return ProxyDecision(forward=True)

    async def probe():
        from mcp import StdioServerParameters

        params = StdioServerParameters(
            command=sys.executable,
            args=["-c", child_server],
            cwd=str(ROOT),
        )
        async with Client(
            params, mode="legacy", raise_exceptions=False, read_timeout_seconds=5.0
        ) as downstream:
            proxy = create_proxy_server(downstream, gate)
            async with Client(
                proxy, raise_exceptions=False, read_timeout_seconds=5.0
            ) as host:
                tools = await host.list_tools()
                assert [tool.name for tool in tools.tools] == ["effect"]

                first = await host.call_tool("effect", {"text": "first"})
                assert first.is_error is False
                assert first.content[0].text == "1:first"

                blocked = await host.call_tool("effect", {"text": "BLOCK"})
                assert blocked.is_error is True
                assert json.loads(blocked.content[0].text)["pea_action"] == "refuse"

                second = await host.call_tool("effect", {"text": "second"})
                assert second.is_error is False
                assert second.content[0].text == "2:second"

    anyio.run(probe)


def test_validate_envelope_rejects_bare_stage():
    try:
        validate_envelope({"stage": "pre_action"})
    except Exception:
        return
    raise AssertionError("invalid envelope must raise")
