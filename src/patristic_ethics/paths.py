"""Default paths that work from a source checkout and an installed wheel."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[1]


def _repo_or_bundled(relative: str) -> Path:
    repo = REPO_ROOT / relative
    if repo.exists():
        return repo
    return PACKAGE_ROOT / "data" / relative


def default_db_path() -> Path:
    return _repo_or_bundled("corpus/units.db")


def default_policy_path() -> Path:
    return _repo_or_bundled("policy/rules.json")


def default_runtime_db_path() -> Path:
    configured = os.environ.get("PEA_RUNTIME_DB")
    if configured:
        return Path(configured)
    repo = REPO_ROOT / "corpus" / "runtime.db"
    if repo.parent.exists():
        return repo
    return Path.home() / ".local" / "share" / "patristic-ethics" / "runtime.db"
