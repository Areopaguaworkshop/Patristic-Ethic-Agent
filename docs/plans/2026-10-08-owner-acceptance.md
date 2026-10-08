# Owner and environment acceptance packet — 2026-10-08

All six identified engineering packages E1–E6 are implemented through engineering step 18. There are **zero remaining identified code packages** in that backlog. This does not mean every milestone is accepted: **M2 is complete; M0/M1/M3/M4/M5/M6 remain partial**. New failures can create further engineering work. The frozen version remains experimental.

## Remaining work, in order

| Work | Prepared material | Needed decision/evidence |
|---|---|---|
| Adopt the ethical scope and pastoral response policy | [Constitution](../../policy/constitution.md), [rules](../../policy/rules.json), [canonical plan](2026-10-06-pea-implementation-plan.md) | Owner/content reviewer confirms principles, application limits, tradition-specific disputes, constructive tone and urgent-care handling. Approval must be real; code has not relabelled drafts as reviewed. |
| Review patristic corpus and rights | [Seed](../../corpus/seed.jsonl), [source audit/review packet](../research/2026-10-07-corpus-source-audit.md) | Review 40 source-verified texts plus the nonquotable placeholder, interpretation notes/edition attribution/licensing, and any disputed applications. Exact-text verification is already done; editorial review is distinct. |
| Establish a usable inference/deployment environment | [Diagnostic](../evaluation/ollama-diagnostic.md), [host coverage](../host-coverage.md), [operator boundary](../operator-boundary.md) | Choose a backend meeting reliability/latency/privacy needs; provide credentials only to the configured host environment when needed. Demonstrate separate operator identity/database/credential denial before enabling shell-capable review profiles. Do not send secrets in chat. |
| Collect remaining live host evidence | [Native conformance](../evaluation/host-conformance.md), [OpenCode](../hosts/opencode.md), [Codex](../hosts/codex.md), [Claude](../hosts/claude-code.md) | Runs must prove installed-host delivery, history-dependent judgments, covered action blocking, controlled generated-answer withholding, effective managed policy and continuation/compaction. Synthetic checks already pass. Codex controlled mode stays unsupported until a preventive boundary exists. |
| Supply untouched holdouts and independent judgments | [Rubric](../../eval/rubric.md), [comparison](../evaluation/response-comparison.md), [grade ingestion](../evaluation/human-grading.md), [disagreements](../evaluation/disagreements.md) | At least 120 human-reviewed base cases, planned balance/principle/multi-turn coverage, separate ambiguity set, family separation and hash-locked owner manifests. Independent content and care grades are required; missing judgments remain ungraded. |
| Decide release scope after gates are evaluated | [Profile](../releases/pea-0.0.1-experimental-profile.json), [snapshot](../releases/pea-0.0.1-experimental-snapshot.json) | Preserve originals, resolve disputes explicitly, rerun the declared configuration and inspect thresholds. Keep experimental/unsupported labels where evidence is absent. A file hash verification is not release approval. |

The next owner action is review of the constitution and source/application packet. Actual human approval and reviewer grades cannot be supplied by the coding agent. Environment-dependent runs can resume once the required backend/host/admin conditions exist; they are not automatically the owner's coding responsibility.

Frozen source/configuration integrity can be checked locally:

```sh
.venv/bin/python eval/freeze.py --verify docs/releases/pea-0.0.1-experimental-snapshot.json
```

Any later code/policy/corpus/evidence edit invalidates this snapshot. Preserve it, then produce a new versioned profile/snapshot for the next evaluation. Do not publish exposed/tuned development families as an untouched holdout.
