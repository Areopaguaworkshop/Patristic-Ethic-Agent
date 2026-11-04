# Bundled PEA defaults

This directory is included in the Python wheel so `pea-mcp` works outside a
source checkout.

- `policy/rules.json`: owner-approved policy 0.1.0.
- `corpus/units.db`: derived corpus index built from `corpus/seed.jsonl`.

The source checkout remains canonical. Rebuild these copies when the policy or
corpus changes, then rebuild the wheel.
