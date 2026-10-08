# Reviewer disagreements

Status: pending actual independent reviews; no human disputes or resolutions have been recorded.

`eval/grade.py` stores the canonical machine-readable disagreement list in each reviewed comparison artifact, bound by the original report/response hashes and record identity. Every disputed dimension retains the individual reviewer scores/applicability/task judgments, reasons and dates. Resolution starts as `pending owner decision`; the tool never silently averages or resolves it.

When the owner reviews a dispute, append its source report hash, scenario ID, repeat, condition, dimension, individual judgments, resolution/reason, resolver and date here. Preserve the original grade records and artifact. A resolution does not retroactively make exposed scenario families untouched holdout evidence.

See [grade ingestion and reporting](human-grading.md). Reviewer judgments and owner resolution remain deferred until engineering work is complete.
