# pea-mcp

Thin stdio launcher for the Patristic Ethics Agent MCP server.

```sh
npx pea-mcp
```

The launcher prefers `uvx --from patristic-ethics pea-mcp` and falls back to
`python3 -m patristic_ethics.mcp_server`. It never installs packages silently.
Install `uv` or the Python package `patristic-ethics` first.

The Python engine contains the policy, corpus, MCP tools, review store, and
audit. This npm package only forwards stdio and signals.

Experimental software. Not a qualified ethical authority or a release.
