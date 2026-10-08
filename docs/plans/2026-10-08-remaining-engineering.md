# Remaining engineering work after step 13

This audit reconciles the original instruction and the M0–M6 implementation plan with the current runtime paths on 2026-10-08. It is a finite backlog of identified engineering gaps, not a promise that no new defect will be discovered. Milestone completion requires both implementation and acceptance evidence. Owner review and deployment-dependent evidence follow engineering work.

## Engineering backlog

| ID | Requirement and code evidence | Completion check | Status |
|---|---|---|---|
| E1 | M4/M5 evaluator outage: `ControlledClient.run` called the assessor directly at input/output; unexpected exceptions escaped. | Both phases return static withholding, prevent unreviewed release, exclude exception text and recover safely on the next turn. Missing/unknown results and failure-bearing proceed results cannot forward. | Completed in step 13; shared implementation covers both controlled clients. |
| E2 | §5 context limits and M4/M5 history: controlled history grows without a bound; OpenCode mapping reports complete whenever a message array is returned despite dropping nontext rows. `OllamaInterpreter._prompt` omits history completeness/errors and the summary source ID. | Bound the supplied context, disclose omissions/loss to the interpreter, preserve source IDs and session isolation, and test history-dependent requests with missing antecedents. Do not claim a host's compaction is lossless. | Completed in step 14; synthetic Python and Bun checks pass, live compaction semantics remain unproven. |
| E3 | M2 item 5: `guidance.revise_once` exists and has isolated tests, but the controlled runtime does not call it. | At most one explicitly configured revision; assess the revised candidate again, release only checked content, fall back to PEA guidance/static withholding, and never resume a host transcript containing rejected content. No extra generation by default. | Completed in step 15; optional runtime revision and failure/recheck regressions pass. |
| E4 | M5 item 4: host tests exist in separate Python/TypeScript suites, but the same conformance scenario matrix is not run across all three adapters. | Reuse one small fixture set for benign/harmful/ambiguous input, covered tool actions, evaluator outage and context isolation; report mode/version and unsupported paths. Synthetic success must remain distinct from live delivery. | Completed in step 16; one 23-case native matrix runs across Python/Bun adapters, with mode-specific limitations recorded. |
| E5 | M6 items 2–3: comparison records leave `human_grades` null; rubric exists, but there is no runnable grade-ingestion/disagreement report. | Validate external reviewer grades bound to evaluated records; report grounding, care, task completion and disagreement with denominators. Never invent reviewer judgments or treat missing grades as passes. | Completed in step 17; external grades are hash-bound and validated, with explicit missing coverage and unresolved disagreement reporting. Owner supplies judgments later. |
| E6 | M6 item 5: report hashes and known limitations exist, but no frozen release-candidate configuration artifact ties policy/corpus/models/host modes/settings and evidence together. | Generate a reproducible configuration/evidence snapshot, retain experimental status until gates pass, and update README run/support instructions. Snapshot creation must not assert release readiness. | Completed in step 18; versioned experimental profile, reproducible source/evidence hash snapshot, drift verification and README instructions are present. No release readiness is asserted. |

After E1–E6, **zero identified engineering work packages remain**. Engineering steps 13–18 closed these six packages. This is not milestone acceptance or a guarantee against new defects. Continue with the [owner/environment acceptance packet](2026-10-08-owner-acceptance.md).

## Environment and host capability evidence

| Dependency | Work still required | Current boundary |
|---|---|---|
| Codex controlled profile (M0/M5) | Demonstrate a preventive no-tools/client display boundary before implementing supported controlled mode. | Explicitly unsupported; the inspected App Server configuration did not establish that boundary. Do not fabricate support. |
| Live native host delivery (M0/M4/M5) | Installed-host runs proving automatic history-dependent judgment and covered action blocking. | Synthetic adapters and process tests cannot substitute for live delivery. |
| OpenCode/Claude controlled hosts (M4/M5) | Real generated-answer screening, trustworthy effective managed policy and continuation/compaction evidence. | Current local model timeouts and synthetic process buffering do not close acceptance. |
| Declared local inference backend (M6) | Successful matched comparisons and measured accuracy/latency. | CPU-only diagnostics and partial smoke results remain experimental; optional tuning is not proof of reliability. |

Attempt available read-only/local checks without asking the owner to redo engineering work. Record failed probes honestly; credentials, machine/admin changes and unsupported host capabilities are not solved by adding speculative code.

## Owner work, last

1. Review the constitution, principle applications, patristic corpus provenance/rights and pastoral guidance; existing seed and policy remain draft-unreviewed.
2. Choose/configure a usable backend and authorize any credential-dependent live-host tests. No paid/cloud inference is implied by this backlog.
3. Deploy separate operator identity and database/credential isolation, then prove denial through every enabled agent tool. Application-level token checks and same-UID tests are insufficient.
4. Supply untouched, reviewed, hash-locked base and ambiguity holdouts, plus independent content/care grades and disputed-case judgments.
5. Evaluate the frozen configuration against release gates and decide whether to publish a bounded experimental release or a qualified release.

After step 15, **M2 is fully implemented and acceptance-complete; six milestones remain partial**. Its bounded revision helper is now integrated into the shared controlled runtime and covered by rechecking/fallback regressions. Live semantic accuracy and latency remain M6 requirements. Other milestones retain the acceptance gaps recorded in the canonical plan.
