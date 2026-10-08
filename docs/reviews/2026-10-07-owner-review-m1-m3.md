# Owner review needed for M1 and M3

This packet collects decisions that code cannot make on the project owner's behalf. Reply with edits or decisions by item number; unresolved items remain marked draft and do not count as consensus.

## M1: policy and corpus

Please review these drafts together:

- [`policy/constitution.md`](../../policy/constitution.md) — principles, refusal boundaries, care and guidance.
- [`policy/rules.json`](../../policy/rules.json) — machine-applied dispositions and topic mappings.
- [`corpus/seed.jsonl`](../../corpus/seed.jsonl) and [`corpus/sources.json`](../../corpus/sources.json) — source text, attribution, rights and retrieval links.
- [`eval/scenarios.jsonl`](../../eval/scenarios.jsonl) — development-only examples; these are not release holdout data.

Decisions that currently need an owner judgment:

1. **P04 fraud threshold:** should direct assistance with theft/fraud be refused, or guided with a warning? The current draft is not aligned on this edge case.
2. **Principle wording and scope:** approve or amend each principle in the constitution, especially where it covers conduct beyond the four firm-refusal categories already chosen (murder, rape, suicide/self-harm, and terrorist recruitment).
3. **Patristic evidence:** confirm, dispute, or leave each named author/work/locus as an evidence gap. Do not approve an attribution or quotation from a model suggestion alone.
4. **Scripture and corpus units:** approve only source spans whose edition/translation, attribution, rights status and text are accurate. Flag any source that should not be used.
5. **Disagreement:** state which traditions or interpretations must be shown as differing rather than collapsed into a single answer.

Until reviewed, policy and corpus labels remain `draft-unreviewed`; the runtime may test mechanics against them, but release reporting must label those results experimental.

## M3: deployment operator boundary

The code prevents review approval through the agent-facing MCP tools, but the current same-user environment cannot stop a shell-capable agent from reading the operator token or editing the SQLite file. The required deployment evidence needs one of:

- a separate OS account for operator-owned review state and resolution; or
- a sandbox boundary with equivalent file and process isolation.

Please identify which boundary is available on the intended deployment machine. Until that boundary is tested, reviewable actions must stay disabled in the controlled profile and M3 remains partial.
