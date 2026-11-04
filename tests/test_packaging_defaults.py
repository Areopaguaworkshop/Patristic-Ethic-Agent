"""Console-script defaults must work outside the source checkout."""
from pathlib import Path

from patristic_ethics import cli, controlled, paths
from patristic_ethics.runtime_store import RuntimeStore


def test_console_defaults_are_absolute_packaged_paths():
    for value in (
        cli.DEFAULT_DB,
        cli.DEFAULT_POLICY,
        controlled.DEFAULT_DB,
        controlled.DEFAULT_POLICY,
        paths.default_runtime_db_path(),
    ):
        assert Path(value).is_absolute()


def test_runtime_store_creates_a_missing_parent(tmp_path):
    db = tmp_path / "nested" / "runtime.db"
    store = RuntimeStore(db)
    store.conn.close()
    assert db.exists()
