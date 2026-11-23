# PEA 0.0.3 release-candidate rehearsal — 2026-11-23

Status: **build, install, and registry checks pass; nothing is published.**
The release remains blocked by the M6 human gates (independent grades and the
false-intervention baseline), the Claude live-login check, and production
review mediation. This report prepares the release; it does not authorize it.

## Version availability

Checked 2026-11-23:

| Registry | Package | Published versions |
| --- | --- | --- |
| PyPI | `patristic-ethics` | `0.0.1` |
| npm | `pea-mcp` | `0.0.0-stage`, `0.0.1` |

`0.0.3` is unused on both registries. The version is bumped in
`pyproject.toml`, `src/patristic_ethics/__init__.py`,
`packages/mcp/package.json`, and the performance freeze profile.

## Python artifacts

Built with `uv build` from the branch `pea/performance-improvements`; the
release commit is the one containing this report.

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `dist/patristic_ethics-0.0.3-py3-none-any.whl` | 129119 | `abc36c852d60995e54e96efb45bc48426c030829a737ad294b8e3e04a91f0fae` |
| `dist/patristic_ethics-0.0.3.tar.gz` | 113144 | `c0df90df80fe4fb444e8d4b72d7c117e0e0c9e8e988ed4e12ada8fd11f7286fc` |

Checked:

- wheel metadata: `Name: patristic-ethics`, `Version: 0.0.3`,
  `Requires-Python: >=3.11`.
- wheel bundles `patristic_ethics/data/corpus/units.db` and
  `scripture.jsonl` (13 KJV records, P01–P10).
- sdist uses the explicit allowlist: `src`, `corpus/scripture.jsonl`,
  `README.md`, `LICENSE`, `pyproject.toml`. No docs, artifacts, `.slim`,
  `.venv`, `node_modules`, or tests.
- clean-room install outside the checkout (`uv venv` + wheel) reports
  `patristic_ethics.__version__ == "0.0.3"` and exposes all seven scripts:
  `pea`, `pea-mcp`, `pea-controlled`, `pea-controlled-claude`,
  `pea-codex-hook`, `pea-claude-hook`, `pea-operator`.
- installed `pea-mcp` completed an MCP initialize + `tools/list` handshake
  and returned all four tools: `check_action`, `search_corpus`,
  `get_passage`, `cite_father`.
- `uvx twine check` passed the wheel and sdist.

## npm launcher

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `packages/mcp/pea-mcp-0.0.3.tgz` | 5878 | `9f803997212e6edce74cc53af397b31e531bb663c051f4a5f0cff08312d00e2f` |

- `npm test`: 5 passed, 0 failed.
- `npm pack` contains exactly `LICENSE`, `README.md`, `bin/pea-mcp.js`,
  `package.json`; no dependencies and no install lifecycle scripts.
- `node bin/pea-mcp.js --version` prints `0.0.3`.
- With `PEA_MCP_FORCE_PYTHON=1` and `PEA_PYTHON` pointing at the clean-room
  venv, the packed launcher completed the same four-tool MCP handshake.

## Integrity checks

- Secret-pattern scan over the extracted wheel, sdist, and npm tarball found
  no registry, API-key, or private-key markers.
- `eval/freeze.py --profile docs/releases/pea-performance-experimental-profile.json`
  saved 123 file hashes and `--verify` passed. The profile now declares
  `package_version: "0.0.3"` and remains `release_ready: false`.

## Publish — only after the gates and owner approval

The registries are ordered: PyPI first, then npm. The npm launcher resolves
the Python package through `uvx --from patristic-ethics`, so the Python
package must be live first.

```sh
# 1. PyPI (token or trusted publisher; never commit the token)
export UV_PUBLISH_TOKEN=...
uv publish \
  "dist/patristic_ethics-0.0.3-py3-none-any.whl" \
  "dist/patristic_ethics-0.0.3.tar.gz"

# 2. Verify the Python release
uvx --from patristic-ethics pea-mcp --version

# 3. npm (account with 2FA; local publish from the reviewed commit)
cd packages/mcp
npm login
npm publish
npm view pea-mcp version

# 4. Verify the launcher
npx pea-mcp --version
npx pea-mcp        # starts the MCP stdio server; Ctrl-C to stop
```

Use `npm publish --provenance` from CI with OIDC. For a local publish, publish
only from the clean release commit and tag it.

## Current blockers

- No independent reviewer grades or independently labeled scenarios; the
  live baseline also records 17/32 full-PEA clarify outcomes, including
  benign cases, so the false-intervention gate is not met.
- Claude Code live controlled mode remains blocked on an authenticated
  account.
- Production review mediation and a deployment-owned operator store remain
  open.
- No `UV_PUBLISH_TOKEN` is set in this environment and `npm whoami` is not
  authenticated; registry credentials must be supplied for the publish step.

Until those close, keep `0.0.1` as the public experimental version and do not
claim a qualified release. Publishing is distribution, not ethical release.
