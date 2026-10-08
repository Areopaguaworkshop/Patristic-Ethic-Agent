# Shared native-host conformance — 2026-10-08

The same 23 fixtures exercise Codex, Claude Code and OpenCode native adapters: benign/harmful/ambiguous/review/support inputs and tool proposals, assessment outage, malformed/missing/unknown actions, failure-bearing forward results, contradictory semantic dispositions, and session isolation. Fixture SHA-256: `7317fb4feee00d7232152e823676518e36e997c3262cc6489493c98c812d06d0`.

These are development fixtures with scripted assessment results. They verify translation, data collection and enforcement responses; they do not measure semantic judgment, policy accuracy or live host delivery. Python hooks execute their actual handlers with injected assessment runners. Bun executes the actual OpenCode plugin with fixture SDK session data and a synthetic child assessment CLI. No model, paid API or network calls are used.

| Native adapter | Declared mapping version | Input behavior | Covered pre-tool behavior | Context |
|---|---|---|---|---|
| Codex | 0.160.0 | block on refusal/ambiguity/review/outage or invalid result; guide adds context | deny on blocking outcomes, guide adds context | operator-configured hook-observed prior turns; incomplete |
| Claude Code | 2.1.286 | block on refusal/ambiguity/review/outage or invalid result; guide adds context | deny on blocking outcomes, guide adds context | operator-configured hook-observed prior turns; incomplete |
| OpenCode | 1.18.x envelope; prior installed probe 1.18.35 | advisory guidance injection; assessment errors inject nothing | hook throws on blocking outcomes/outage/invalid result; zero local mock effects for those fixtures | bounded text-only SDK snapshot; incomplete |

All three preserve the covered proposed arguments and isolate the target session's earlier text from an unrelated session. The shared Python result validator and corresponding TypeScript check reject missing/unknown actions, failed forward assessments and proceed/non-allow contradictions before mapping authority. OpenCode's native input failure behavior remains advisory; this report does not label it preventive prompt enforcement. Native guide outcomes in its tool hook are audited without injecting corrective context.

Commands:

```sh
.venv/bin/pytest -q tests/integration/test_shared_host_conformance.py
PEA_RUN_BUN_TEST=1 .venv/bin/pytest -q tests/integration/test_shared_host_conformance.py
```

The first runs 46 Python fixture combinations and skips the Bun transport check. The second runs 47 tests, including all 23 OpenCode fixtures in one Bun test; it requires an environment permitting Bun pipe sends. Observed result outside the managed sandbox: **47 passed in 0.86s**, covering 69 host/scenario combinations. The managed sandbox denies Bun pipe sends, so its check is explicitly opt-in.

Before-display prevention is outside this native matrix. OpenCode/Claude controlled-display subprocess tests are separate; Codex controlled mode remains unsupported. Actual managed-policy precedence, installed-host invocation, authoritative transcript/compaction coverage, subagents/background work and host-killed hooks remain unverified or unsupported as recorded in the host docs. These fixtures do not make M0/M4/M5 acceptance-complete.
