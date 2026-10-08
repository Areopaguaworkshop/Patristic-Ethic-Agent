"""Shared test setup.

`corpus/units.db` is a gitignored build artifact, so rebuild it once per session
when a fresh clone has not run `pea corpus build` yet.
"""

from pathlib import Path

import pytest

from patristic_ethics.corpus import build_db

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "corpus" / "units.db"
SEED = ROOT / "corpus" / "seed.jsonl"


@pytest.fixture(scope="session", autouse=True)
def corpus_index() -> None:
    if not DB.exists():
        build_db(SEED, DB)
