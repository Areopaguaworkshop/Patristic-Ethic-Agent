# Pre-publish package review — PEA 0.0.1

Date: 2026-11-03
Reviewer: Orchestrator (automated checks and clean-room install)
Scope: PyPI `patristic-ethics` wheel and sdist; npm `pea-mcp` tarball; the source files those artifacts ship.
Verdict: the local 0.0.1 artifacts are ready for registry review. This is not a qualified ethical release.

## Evidence

- `uv build` produced `dist/patristic_ethics-0.0.1-py3-none-any.whl` and `.tar.gz`.
- The wheel contains `patristic_ethics/data/corpus/units.db` and `patristic_ethics/data/policy/rules.json`.
- `uv pip install` of the wheel in a clean venv succeeded.
- From `/tmp`, `pea assess --backend fake` proceeded without a policy or corpus error.
- From `/tmp`, `pea-controlled` loaded policy and corpus and withheld cleanly when OpenCode was unavailable.
- From `/tmp`, `pea-operator list` printed `[]`; the runtime database parent was created.
- From `/tmp`, `pea-mcp` started the stdio server (timeout exit 124).
- `cd packages/mcp && npm test` passed 5 tests.
- `npm pack --dry-run` reported version 0.0.1, four files, no dependencies, and no install lifecycle scripts.
- `uvx twine check` passes the wheel and the sdist.
- `git diff --check` is clean.

## Not done in this review

- Registry credentials, `uv publish`, and `npm publish`.
- A fresh secret scan against these exact 0.0.1 artifacts.
- Live host acceptance, operator OS isolation, owner holdout, independent grades, and release gates.

## Boundary

Publishing is distribution, not ethical release. Keep 0.0.1 experimental. The policy is approved; the corpus, host acceptance, holdout, independent grades, and release gates remain partial.
