# Publishing PEA 0.0.1

Status: one PyPI package and one npm package are built and smoke-tested
locally. Nothing has been published. Registry credentials are required.

The first public version is 0.0.1. The 0.0.2 review record is historical; the
0.0.2 artifacts must not be published.

## Names

| Registry | Name | Contents |
|---|---|---|
| PyPI | `patristic-ethics` | Python engine, CLI, MCP server, and hook console scripts |
| npm | `pea-mcp` | thin MCP stdio launcher |

The npm package is unscoped because the project does not own the `@pea` npm
scope. Both names returned 404 on the public registries on 2026-10-24. Register
them as soon as possible to prevent name squatting.

Host adapters are not published to npm:

- Codex and Claude Code hooks ship as the Python console scripts
  `pea-codex-hook` and `pea-claude-hook`.
- The OpenCode native plugin runs from `adapters/opencode/index.ts` in a source
  checkout or a git install. See `docs/hosts/opencode.md`.
- Pi remains unverified and unpackaged.

## Build and test

```sh
uv build

rm -rf /tmp/pea-wheel-venv
uv venv /tmp/pea-wheel-venv
uv pip install --python /tmp/pea-wheel-venv/bin/python dist/patristic_ethics-0.0.1-py3-none-any.whl
timeout 2 /tmp/pea-wheel-venv/bin/pea-mcp      # exit 124 means the stdio server started

cd packages/mcp
npm test
npm pack --dry-run
```

The source distribution uses an explicit include allowlist (`src`, `README.md`,
`LICENSE`, `pyproject.toml`). It must not include `.slim/clonedeps`, editor
state, artifacts, or adapter files. `uv build` builds the wheel from the sdist,
which proves the sdist is complete.

## Evidence before publish

- Pre-publish review: `docs/reviews/2026-11-03-package-publish-review-0.0.1.md`.
- `uvx twine check` passes the 0.0.1 wheel and sdist.
- The secret scan was last run against 0.0.2. Rerun it against the 0.0.1
  artifacts before upload.
- Clean-room install: the 0.0.1 wheel installs in a fresh venv, and the console
  scripts run from `/tmp`. The npm tarball contains only `bin/pea-mcp.js`,
  `package.json`, `README.md`, and `LICENSE`; it has no dependencies and no
  install lifecycle scripts.

## Publish PyPI first

```sh
# API token in the environment; never commit it or pass it in a shell that logs
uv publish --token "$PYPI_TOKEN" dist/patristic_ethics-0.0.1*
```

Alternative: `UV_PUBLISH_TOKEN` with `uv publish`, or `twine upload`.

Order matters: `npx pea-mcp` resolves the Python package through `uvx --from
patristic-ethics`, so PyPI must be live first.

## Publish npm second

```sh
cd packages/mcp
npm login          # use an account with 2FA enabled
npm publish        # unscoped packages are public by default
npm view pea-mcp version
```

In CI with OIDC, publish with `npm publish --provenance`. For a local publish,
publish from a clean, reviewed commit and tag it.

## Verify after publish

```sh
npx pea-mcp --version
npx pea-mcp        # starts the MCP stdio server; Ctrl-C to stop
```

Generic MCP host configuration: command `npx`, args `["pea-mcp"]`.

## Credential hygiene

- `$PYPI_TOKEN` is read from the environment. Do not put it in a file, a README,
  npm metadata, or a command that is captured in logs.
- `npm login` stores the npm token in `~/.npmrc`. That file is outside the repo
  and was not present in any artifact.
- Use 2FA on both registries and revoke tokens after the release.
- API keys for remote inference stay in the host environment. The launcher
  forwards the environment unchanged and never reads or prints a key.

## Boundary

Publishing is distribution, not ethical release. Keep `0.0.1` experimental. The
policy is approved; the corpus, host acceptance, holdout, independent grades, and
release gates remain partial. Do not claim a qualified release or OS operator
isolation.
