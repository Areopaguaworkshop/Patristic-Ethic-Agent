"""Offline SDK pin checks (no network).

Verifies the pinned MCP SDK (>=2.3,<3) and ollama client (>=0.6.3,<0.7)
behave as researched: in-process MCPServer + Client with structured output
derived from the tool's return annotation, and tool errors surfacing as
is_error results.
"""

from __future__ import annotations

from pathlib import Path
import tomllib

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


def test_package_installs_user_facing_cli_commands() -> None:
    project = tomllib.loads(
        (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert project["project"]["scripts"] == {
        "pea": "patristic_ethics.cli:main",
        "pea-controlled": "patristic_ethics.controlled:main",
        "pea-controlled-claude": "patristic_ethics.claude_controlled:main",
        "pea-operator": "patristic_ethics.operator:main",
    }


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

    async with Client(server, raise_exceptions=False, read_timeout_seconds=2.0) as client:
        ok = await client.call_tool("echo", {"text": "PEA"})
        assert ok.structured_content == {"text": "PEA"}

        err = await client.call_tool("boom", {})
        assert err.is_error


def test_inprocess_mcp_structured_output() -> None:
    anyio.run(_probe_server)
