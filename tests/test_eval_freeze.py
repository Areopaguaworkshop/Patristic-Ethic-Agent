import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_freeze", ROOT / "eval/freeze.py")
freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freeze)


def project(tmp_path):
    for directory in (*freeze.SOURCE_DIRS, "corpus", "docs"):
        (tmp_path / directory).mkdir()
    (tmp_path / "src/app.py").write_text("print('test')\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.0.1"\n')
    (tmp_path / "uv.lock").write_text("test lock\n")
    (tmp_path / "corpus/seed.jsonl").write_text("fixture\n")
    (tmp_path / "corpus/units.db").write_bytes(b"test corpus")
    (tmp_path / "docs/evidence.md").write_text("Synthetic evidence, not release acceptance\n")
    profile = dict(schema_version=1, id="test-experimental", package_version="0.0.1",
                   status="experimental", release_ready=False,
                   evidence=[dict(path="docs/evidence.md", scope="synthetic only")])
    (tmp_path / "profile.json").write_text(json.dumps(profile))
    return profile


def test_deterministic_snapshot_includes_inputs_and_ignores_private_runtime(tmp_path):
    project(tmp_path)
    (tmp_path / "corpus/runtime.db").write_text("private")
    (tmp_path / "src/__pycache__").mkdir()
    (tmp_path / "src/__pycache__/app.py").write_text("ignored cache")
    snapshot = freeze.build_snapshot(tmp_path, "profile.json")
    assert snapshot == freeze.build_snapshot(tmp_path, "profile.json")
    assert snapshot["release_ready"] is False
    assert "corpus/runtime.db" not in snapshot["files"]
    assert "src/__pycache__/app.py" not in snapshot["files"]
    assert "uv.lock" in snapshot["files"]
    (tmp_path / "src/app.py").write_text("changed")
    changed = freeze.build_snapshot(tmp_path, "profile.json")
    assert changed["inputs_sha256"] != snapshot["inputs_sha256"]


@pytest.mark.parametrize("field,value", [("release_ready",True),("status","release"),
                                         ("schema_version",True),("package_version","9.0")])
def test_invalid_release_claim_or_version_rejected(tmp_path, field, value):
    profile = project(tmp_path)
    profile[field] = value
    (tmp_path / "profile.json").write_text(json.dumps(profile))
    with pytest.raises(ValueError):
        freeze.build_snapshot(tmp_path, "profile.json")


@pytest.mark.parametrize("path", ["../secret", "/tmp/secret", ".aws/credentials", "corpus/runtime.db"])
def test_evidence_cannot_escape_project_or_read_hidden_inputs(tmp_path, path):
    profile = project(tmp_path)
    profile["evidence"][0]["path"] = path
    (tmp_path / "profile.json").write_text(json.dumps(profile))
    with pytest.raises(ValueError):
        freeze.build_snapshot(tmp_path, "profile.json")


def test_symlink_source_rejected(tmp_path):
    project(tmp_path)
    target = tmp_path / "secret"
    target.write_text("private")
    (tmp_path / "src/linked.py").symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        freeze.build_snapshot(tmp_path, "profile.json")


def test_freeze_verify_detects_changes_and_never_overwrites(tmp_path, monkeypatch, capsys):
    project(tmp_path)
    monkeypatch.setattr(freeze, "ROOT", tmp_path)
    output = tmp_path / "snapshot.json"
    assert freeze.main(["--profile", "profile.json", "--output", str(output)]) == 0
    raw = output.read_bytes()
    assert freeze.main(["--verify", str(output)]) == 0
    assert freeze.main(["--profile", "profile.json", "--output", str(output)]) == 2
    assert output.read_bytes() == raw
    (tmp_path / "docs/evidence.md").write_text("changed evidence")
    assert freeze.main(["--verify", str(output)]) == 2
    assert "docs/evidence.md" in capsys.readouterr().err
    assert output.read_bytes() == raw
    assert freeze.main(["--verify", str(output), "--profile", "profile.json"]) == 2


def test_malformed_snapshot_returns_validation_error(tmp_path, monkeypatch):
    project(tmp_path)
    monkeypatch.setattr(freeze, "ROOT", tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"profile_path":"profile.json", "files":[]}))
    assert freeze.main(["--verify", str(bad)]) == 2
