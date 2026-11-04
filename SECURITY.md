# Security Policy

## Supported versions

`0.0.1` is an experimental release. Security fixes are applied to the current
`main` branch; older experimental versions are not supported.

## Reporting a vulnerability

Do not open a public issue for a security problem. Use GitHub's private
vulnerability reporting / Security Advisories for this repository. Include:

- the affected version and host mode (CLI, MCP, hook, controlled client),
- a minimal reproduction,
- the observed impact,
- any relevant logs with secrets removed.

Do not include API keys, operator tokens, session transcripts, or personal
data in a report.

## Scope

Reports are welcome for the assessment core, MCP server and proxy, host
adapters, review/runtime store, packaging, and corpus/policy loading.

Known limits are documented in `README.md` and `docs/operator-boundary.md`:
operator OS isolation is not proven, live host acceptance is partial, and the
project is not a qualified ethical authority.

## Disclosure

Please allow time for a fix and a coordinated disclosure. The maintainers will
credit reporters who want credit, without publishing personal contact details.
