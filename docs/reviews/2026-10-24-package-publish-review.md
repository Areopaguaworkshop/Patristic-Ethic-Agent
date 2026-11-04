# Pre-publish package review — PEA 0.0.2 (historical)

> Historical note: this review covers the 0.0.2 artifacts. The first public version is 0.0.1; rerun the review against the 0.0.1 artifacts before publishing.

Date: 2026-10-24
Reviewer: Orchestrator (direct review plus automated scans)
Scope: PyPI `patristic-ethics` wheel and sdist; npm `pea-mcp` tarball; the source
files those artifacts ship.
Verdict: no publish blocker remains in the artifacts. Publish PyPI first, then
npm. Owner credentials are still required. Distribution only; not a qualified
ethical release.

## 1. Findings

### 1.1 Blocker found and fixed: the sdist shipped unrelated repository files

The first sdist built in this session contained 230 entries, including
`.slim/clonedeps/repos/...` (cloned third-party repositories), `.code-review-graph/`,
`adapters/opencode/`, `artifacts/`, `uv.lock`, and root policy essays. Cause:
`.ignore` un-ignores `.slim/clonedeps/repos`, so the hatchling defaults included
them.

Fix: an explicit sdist allowlist in `pyproject.toml`:

```toml
[tool.hatch.build.targets.sdist]
include = ["/src", "/README.md", "/LICENSE", "/pyproject.toml"]
```

The rebuilt sdist has 33 entries (104K) and the wheel has 33 entries (120K).
`uv build` builds the wheel from the sdist, which proves the sdist is complete.
No `.slim`, `.code-review-graph`, `artifacts/`, top-level `corpus/`, or adapter
files remain.

### 1.2 npm distribution reduced to one unscoped package

The owner does not hold the `@pea` npm scope. The four scoped packages were
collapsed to one unscoped package, `pea-mcp` (available: HTTP 404 on 2026-10-24).
The Codex and Claude Code hooks remain Python console scripts in the PyPI
package. The OpenCode plugin remains source-only. No npm workspace is needed.

### 1.3 Launcher review

`packages/mcp/bin/pea-mcp.js`:

- zero runtime dependencies; no `preinstall`/`postinstall` lifecycle scripts;
- `files` allowlist: `bin`, `README.md`, `LICENSE`, plus `package.json`; the
  packed tarball contains exactly four files;
- `spawn(..., { shell: false })`; no shell interpolation of arguments;
- inherits the environment unchanged, which is required for `PEA_API_KEY`
  passthrough; the launcher never reads, prints, or stores a key;
- `--version`/`--help` are intercepted only as the first argument, so they cannot
  shadow a host argument elsewhere;
- `uvx --version` probe now has a 5s timeout, so a hung binary cannot block
  startup; a timeout falls back to Python;
- ENOENT prints one install command and exits 1; child exit codes are forwarded;
  signals are forwarded with a double-kill guard;
- Node 18 compatible (uses `fileURLToPath`, not `import.meta.dirname`).

Known limitations: Windows signal and `python` resolution are not tested; a
local publish has no provenance attestation (use CI); `uvx` needs the PyPI
package to exist, so publish order matters.

### 1.4 Credential and secret scan

Scanned the 139 files that make up the wheel, sdist, npm tarball, and their
publishable source for:

- PyPI (`pypi-...`), npm (`npm_...`), GitHub (`ghp_`, `gho_`, `github_pat_`),
  Anthropic (`sk-ant-...`), OpenAI-style (`sk-...`), AWS (`AKIA...`), and Slack
  (`xox...`) tokens;
- private-key headers, `_authToken`, bearer tokens, and literal
  key/secret/password assignments.

Result: **0 hits**. No `.env`, `.npmrc`, `.pypirc`, `id_rsa`, `.pem`, or
credential/secret filenames in the artifacts. `~/.npmrc` exists and holds the
owner's npm token outside the repository; it was not read into any artifact.

### 1.5 Clean-room verification

| Check | Result |
|---|---|
| Install wheel in a fresh venv, start `pea-mcp` | exit 124 (server running) |
| `uv build` | wheel built from the sdist |
| `twine check` wheel + sdist | PASSED |
| npm tests | 4 pass, 0 fail |
| Install packed tarball in an empty project | ok, 0 vulnerabilities |
| `pea-mcp --version` | `0.0.2` |
| `pea-mcp --help` | shows `npx pea-mcp` |
| Start via Python fallback from the clean-room install | exit 124 (server running) |
| Missing interpreter | exit 1 with install help |
| Python test suite | 576 passed, 10 skipped |

### 1.6 `backnotprop/pstack`

`backnotprop/pstack` exists, but it is a standalone mirror of
`cursor/plugins/pstack`: a collection of agent skills, not a package verifier.
It was not installed because installing a skill pack would change the agent
configuration and does not verify npm/PyPI artifacts. Its relevant principle
(`prove-it-works`) was applied directly through the clean-room install, tarball
inspection, and runtime checks above. If the owner wants the skills themselves,
install them separately with `npx skills add backnotprop/pstack`.

## 2. Residual risks

- The PyPI and npm names are unregistered; register them to prevent squatting.
- The first `npx pea-mcp` run needs network access for `uvx` to fetch the Python
  package; later runs use the uv cache.
- Remote provider keys are inherited by the Python child; this is required for
  inference and the child is the trusted engine.
- Host acceptance (OpenCode live, Codex, Claude) remains partial; package
  distribution does not change that.
- The corpus, holdout, grades, and release gates remain partial. `0.0.2` is
  experimental.

## 3. Verdict

The artifacts are clean and reproducible. Publish in this order:

1. PyPI: `uv publish --token "$PYPI_TOKEN" dist/patristic_ethics-0.0.2*`
2. npm: `cd packages/mcp && npm login && npm publish`

Then verify `npx pea-mcp --version` and `npx pea-mcp`.
