# PEA MCP and npm distribution — plan

Date: 2026-10-24
Status: implemented for one unscoped npm package (`pea-mcp`) plus the PyPI package; nothing has been published. The `@pea` npm scope was dropped because the owner does not hold it. Host adapters stay source/PyPI-only for now.

## 1. Goal

Publish PEA as:

1. an MCP server that any compatible host can launch;
2. a thin npm launcher for Node-based hosts;
3. host-specific plugin packages for OpenCode, Codex, Claude Code, Pi, and later hosts.

The Python engine remains the source of truth. The npm packages must not fork the policy, corpus, or assessment logic.

## 2. Recommended architecture

```text
Host plugin / MCP client
  -> pea-mcp (npm launcher, stdio)
  -> Python engine (PyPI package `patristic-ethics`)
  -> policy + corpus + interpreter + runtime store
```

Why a thin launcher:

- no second implementation of the policy;
- one place for citation verification and audit;
- smaller npm surface and faster review;
- the Python package is already the tested runtime.

Trade-off: the host needs Python 3.11+ and the Python package. A bundled binary is larger and platform-specific. A full TypeScript port is a separate project and should not be the first release.

### 2.1 Why pure TypeScript is a port, not a wrapper

The current engine is Python: 6,508 source lines and 7,390 test lines. It includes the policy engine, CSL validators, SQLite/FTS5 corpus access, runtime review store, controlled clients, evaluation harness, and four MCP tools. The corpus database is SQLite with FTS5; a Node-only package needs a native SQLite addon and a bundled database.

A pure TypeScript MCP server therefore requires:

- a second policy and disposition engine with parity tests;
- a second corpus/CSL/retrieval layer;
- a second review store and MCP server;
- a second controlled-client and evaluation harness;
- dual maintenance for every safety fix.

A thin npm launcher is roughly 100–200 lines and keeps one logic source. A pure TypeScript port is justified only if "no Python at runtime" is a hard product requirement. Choose it deliberately as a port project, not as a packaging step.

## 3. Package matrix

| Package | Registry | Contents | Host |
|---|---|---|---|
| `patristic-ethics` | PyPI | engine, CLI, MCP server, hook console scripts | all |
| `pea-mcp` | npm | `pea-mcp` stdio launcher; Python check | generic MCP |

One npm package only. `pea-mcp` is unscoped because the project does not own the
`@pea` scope. The OpenCode plugin is used from `adapters/opencode`; Codex and
Claude Code hooks are Python console scripts. Pi and a terminal wrapper remain
unpackaged. Both published names returned 404 on 2026-10-24.

## 4. Install experience

Generic MCP host:

```sh
npx pea-mcp
```

OpenCode: add the MCP server `npx pea-mcp`, or load the native plugin from
`adapters/opencode/index.ts` in a checkout. Codex and Claude Code: add the MCP
server, or call `uvx --from patristic-ethics pea-codex-hook` and
`uvx --from patristic-ethics pea-claude-hook`. Verify snippets against the
installed host version before publication.

## 5. Python packaging

- Add a `pea-mcp` console script pointing to `patristic_ethics.mcp_server:main`.
- Publish the wheel to PyPI.
- Test `uvx patristic-ethics` and `python -m patristic_ethics.mcp_server`.
- Keep the version aligned with the experimental profile (`0.0.1`).

## 6. npm packaging

- Publish one unscoped package, `pea-mcp`; no npm workspace and no `@pea` scope.
- The launcher spawns Python and forwards stdio and signals.
- Check uvx/Python at startup and print a clear install command if missing.
- Do not download or execute installers silently.
- No telemetry, no secrets, no hosted service, zero runtime dependencies.
- Use `npm publish --provenance` in CI; omit it for a local publish.
- Ship Apache-2.0 in the package and the repository.

## 7. Host plugins

### OpenCode

Package the existing TypeScript adapter. It already calls the frozen CLI and handles covered pre-tool failures. Publish with `@opencode-ai/plugin` as a peer dependency and test with Bun.

### Codex

Ship a hook script and an MCP configuration snippet. Controlled mode remains unsupported. Native hooks are covered protocol paths only; live delivery must be tested per host version.

### Claude Code

Ship a hook script and an MCP configuration snippet. Controlled print/JSON mode remains experimental. Test output withholding and continuation separately.

### Pi

Verify Pi's extension surface before coding. If it supports MCP, use `@pea/mcp`; if it supports plugins, add a small adapter. Do not invent a plugin API.

## 8. Release and safety gates

Publishing npm packages is distribution, not ethical release.

- Keep the experimental label in the package description and README.
- Do not claim OS operator isolation; the owner skipped it.
- Do not claim a qualified release.
- The policy approval, holdout, human grades, and live host gates remain separate.
- Remote provider keys stay in the host environment; never in npm metadata.

## 9. Phases

1. Owner approves the thin-launcher plan, licence, and host order.
2. Add `pea-mcp`; build and test the Python wheel and sdist.
3. Create unscoped `pea-mcp`; test MCP handshake and stdio forwarding.
4. Run the pre-publish review and clean-room install.
5. Add Claude Code and Codex hooks as Python console scripts; verify snippets.
6. Research and add Pi only after its plugin surface is confirmed.
7. Add CI provenance, versioning, and release notes.
8. Publish PyPI first, then npm, as an experimental preview.

## 10. Acceptance

- `npx pea-mcp` starts the MCP server and lists the four tools.
- A generic MCP client completes a `check_action` round trip.
- The OpenCode adapter loads from the checkout and blocks a covered harmful tool call.
- Claude Code and Codex hook snippets are tested against recorded host versions.
- No secret, private transcript, or corpus database is packaged.
- The package README states experimental status and unsupported paths.
- Published artifacts have provenance and immutable versions.

## 11. Open decisions

1. npm scope: resolved by dropping `@pea`; publish one unscoped package, `pea-mcp`.
2. Code licence: Apache-2.0 selected.
3. Python requirement vs bundled binary vs TypeScript port.
4. Host order: OpenCode, Claude Code, and Codex in parallel; Pi after host research.
5. Whether the published package defaults to local Ollama, remote providers, or fake.
6. Which Pi product and plugin surface the owner means.
