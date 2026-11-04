# Contributing

Contributions are welcome. This project combines code, policy, and a
rights-sensitive corpus, so not every change is a normal code change.

## Setup

```sh
uv sync --frozen --extra dev
uv run pytest -q
```

The npm launcher has its own tests:

```sh
cd packages/mcp
npm test
```

## What to change

- Code and tests: open a pull request with the smallest complete change.
- Policy or constitution: describe the ethical and pastoral reasoning. Policy
  changes require owner review; do not present unreviewed material as settled.
- Corpus or citations: preserve `rights_status`, `rights_evidence`, exact text,
  and provenance. Do not add copyrighted text without a compatible licence.
- Host adapters: state the host version and whether the evidence is live or
  synthetic. Do not describe a synthetic contract test as live enforcement.

## Pull request checklist

- [ ] Tests pass with `uv run pytest -q` and `cd packages/mcp && npm test`.
- [ ] No credentials, tokens, personal paths, or session transcripts are added.
- [ ] New corpus records have rights evidence and a review status.
- [ ] Behaviour changes have a regression test.
- [ ] Documentation says what is verified and what remains unproven.

## Security

Report vulnerabilities privately as described in `SECURITY.md`. Do not open a
public issue for a vulnerability.

## Licence

By contributing, you agree that your contribution is licensed under the
Apache License 2.0 in `LICENSE`. Third-party corpus text remains under its
recorded rights; see `DATA_RIGHTS.md`.
