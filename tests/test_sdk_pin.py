"""Offline SDK pin checks (no network).

Verifies the pinned MCP SDK (>=2.3,<3) and ollama client (>=0.6.3,<0.7)
behave as researched: in-process MCPServer + Client with structured output
derived from the tool's return annotation, and tool errors surfacing as
is_error results.
"""

from __future__ import annotations

import anyio
import mcp
import ollama
from mcp import Client
from mcp.server import MCPServer
from pydantic import BaseModel


def test_imports_pinned() -> None:
    assert mcp is not None
    assert ollama is not None
    # ollama 0.6.x exposes both sync and async clients at top level.
    assert hasattr(ollama, "Client") and hasattr(ollama, "AsyncClient")
    # MCP 2.x exposes the in-process Client at top level.
    assert hasattr(mcp, "Client")


class Echo(BaseModel):
    text: str


async def _probe_server() -> None:
    server = MCPServer("pea-sdk-pin")

    @server.tool()
    def echo(text: str) -> Echo:
        """Return the text in a structured result."""
        return Echo(text=text)

    @server.tool()
    def boom() -> Echo:
        """Always raises; the client must see an error result."""
        raise RuntimeError("PEA_TEST_ERROR")

    async with Client(server, raise_exceptions=False, read_timeout_seconds=30.0) as client:
        ok = await client.call_tool("echo", {"text": "PEA"})
        assert ok.structured_content == {"text": "PEA"}

        err = await client.call_tool("boom", {})
        assert err.is_error


def test_inprocess_mcp_structured_output() -> None:
    anyio.run(_probe_server)