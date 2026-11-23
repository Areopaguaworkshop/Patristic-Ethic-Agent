# Publishing PEA

PyPI and npm both list 0.0.1 as the latest version as of 2026-11-23.
Prepare a new version after the acceptance gates pass and verify that its
version is unused on both registries. Registry credentials are required.

The first public version is 0.0.1. The 0.0.2 artifacts belong to the
historical experimental review. Use 0.0.3 or a later unused version for
the next release.

## Names

| Registry | Name | Contents |
|---|---|---|
| PyPI | `patristic-ethics` | Python engine, CLI, MCP server, and hook console scripts |
| npm | `pea-mcp` | thin MCP stdio launcher |

The npm package is unscoped because the project does not own the `@pea` npm
scope.

Host adapters are not published to npm:

- Codex and Claude Code hooks ship as the Python console scripts
  `pea-codex-hook` and `pea-claude-hook`.
- The OpenCode native plugin runs from `adapters/opencode/index.ts` in a source
  checkout or a git install. See `docs/hosts/opencode.md`.
- Pi remains unverified and unpackaged.

## Build and test

```sh
uv build

pea_version=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
pea_rehearsal=$(mktemp -d /tmp/pea-wheel-venv.XXXXXX)
uv venv "$pea_rehearsal"
uv pip install --python "$pea_rehearsal/bin/python" "dist/patristic_ethics-${pea_version}-py3-none-any.whl"
timeout 2 "$pea_rehearsal/bin/pea-mcp"   # check the installed stdio entry point

cd packages/mcp
npm test
npm pack --dry-run
```

The source distribution uses an explicit include allowlist (`src`,
`corpus/scripture.jsonl`, `README.md`, `LICENSE`, `pyproject.toml`). It must not include `.slim/clonedeps`, editor
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
# Provide UV_PUBLISH_TOKEN through the release environment.
uv publish "dist/patristic_ethics-${pea_version}-py3-none-any.whl" \
  "dist/patristic_ethics-${pea_version}.tar.gz"
```

Alternatively, use the configured trusted publisher or `twine upload`.

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

## Performance branch rehearsal — 2026-11-23

The branch built a source distribution and a wheel from that distribution.
A fresh virtual environment outside the checkout installed the wheel, found
all seven console entry points, and validated 13 bundled Scripture records.
The installed Python entry point and the packed npm launcher both completed
an MCP handshake and listed all four tools. The launcher used its explicit
Python fallback with the rehearsed wheel. The five npm launcher tests and
Twine metadata checks for both Python archives passed. Archive inspection
confirmed the bundled corpus and the four expected npm tarball files. A
pattern scan for common registry, API, and private-key markers found none
in these artifacts.

The rehearsal used the checkout's existing version metadata. Once the
release gates pass, repeat these checks from the release commit with the
new version before publishing.
