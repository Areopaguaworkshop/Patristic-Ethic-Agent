"""Offline CLI tests for patristic_ethics.cli (plan §7): capsys + direct argv.

No network. One gated subprocess test exercises the real module entry point.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from patristic_ethics.cli import main
from patristic_ethics.corpus import sha256_text

REPO = Path(__file__).parent.parent
SEED = REPO / "corpus" / "seed.jsonl"
FIXTURES = Path(__file__).parent / "fixtures" / "assess"

TEXT = "Theft is punished by Thy law, O Lord."


def unit(**over):
    base = {
        "id": "u-test-001",
        "principle_ids": ["PEA-P01"],
        "author": "Test Author",
        "work": "Test Work",
        "locus": "1.1",
        "language": "en",
        "edition": "Test Edition",
        "translator": None,
        "source_id": "src-test",
        "source_url": "https://example.test/raw.xml",
        "rights_status": "public-domain",
        "rights_evidence": "https://example.test/rights",
        "retrieved": "2026-10-06",
        "text": TEXT,
        "text_sha256": sha256_text(TEXT),
        "offset_start": None,
        "offset_end": None,
        "cts_urn": None,
        "review_status": "draft-unreviewed",
        "retrieval_verified": True,
    }
    base.update(over)
    return base


def write_seed(tmp_path, units, name="seed.jsonl"):
    path = tmp_path / name
    with path.open("w", encoding="utf-8") as fh:
        for u in units:
            fh.write(json.dumps(u, ensure_ascii=False) + "\n")
    return path


def test_corpus_validate_clean(capsys):
    if not SEED.exists():
        pytest.skip("corpus/seed.jsonl missing")
    assert main(["corpus", "validate", str(SEED)]) == 0
    out = capsys.readouterr().out
    assert "OK" in out


def test_corpus_validate_broken(tmp_path, capsys):
    bad = unit(id="")
    path = write_seed(tmp_path, [bad])
    assert main(["corpus", "validate", str(path)]) == 1
    out = capsys.readouterr()
    assert "PROBLEMS" in out.out
    assert "missing id" in out.err


def test_corpus_validate_malformed_jsonl(tmp_path, capsys):
    path = tmp_path / "seed.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    assert main(["corpus", "validate", str(path)]) == 1
    assert "PROBLEMS" in capsys.readouterr().out


def test_corpus_build_creates_db(tmp_path, capsys):
    seed = write_seed(tmp_path, [unit()])
    db = tmp_path / "units.db"
    assert main(["corpus", "build", str(seed), "--db", str(db)]) == 0
    assert db.exists()
    assert str(db) in capsys.readouterr().out


def test_corpus_build_refuses_broken(tmp_path, capsys):
    seed = write_seed(tmp_path, [unit(text_sha256="wrong")])
    db = tmp_path / "units.db"
    assert main(["corpus", "build", str(seed), "--db", str(db)]) == 1
    assert not db.exists()
    assert "PROBLEMS" in capsys.readouterr().out


def test_corpus_search_json_lines(tmp_path, capsys):
    seed = write_seed(tmp_path, [unit(), unit(id="u-test-002", text="Mercy is good.", text_sha256=sha256_text("Mercy is good."))])
    db = tmp_path / "units.db"
    main(["corpus", "build", str(seed), "--db", str(db)])
    capsys.readouterr()  # discard build output
    assert main(["corpus", "search", "theft", "--db", str(db)]) == 0
    lines = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert lines and lines[0]["id"] == "u-test-001"
    assert set(lines[0]) == {"id", "author", "work", "locus", "language", "text"}


def test_corpus_search_missing_db(tmp_path, capsys):
    assert main(["corpus", "search", "x", "--db", str(tmp_path / "nope.db")]) == 1
    out = capsys.readouterr()
    assert "db not found" in out.err
    assert not out.out.strip()


def test_assess_benign_fake(capsys):
    if not (FIXTURES / "benign.json").exists():
        pytest.skip("benign fixture missing")
    rc = main([
        "assess", "--input", str(FIXTURES / "benign.json"), "--backend", "fake",
        "--db", str(REPO / "corpus" / "units.db"),
        "--policy", str(REPO / "policy" / "rules.json"),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert len(lines) == 1  # protocol-clean: exactly one JSON line
    payload = json.loads(lines[0])
    assert payload["action"] in {"proceed", "guide"}
    assert payload["decision"] is not None
    assert payload["guidance"] is not None and payload["guidance"]["text"]
    assert "audit" in payload
    assert payload["failure"] is None


def test_assess_missing_db_still_assesses(tmp_path, capsys):
    rc = main([
        "assess", "--input", str(FIXTURES / "benign.json"), "--backend", "fake",
        "--db", str(tmp_path / "does-not-exist.db"),
        "--policy", str(REPO / "policy" / "rules.json"),
    ])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[0])
    assert payload["action"] in {"proceed", "guide", "clarify", "review"}


def test_assess_malformed_input_file(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["assess", "--input", str(bad), "--backend", "fake"]) == 2
    out = capsys.readouterr()
    assert json.loads(out.err)["error"] == "malformed input"
    assert not out.out.strip()


def test_assess_malformed_stdin(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", type("S", (), {"read": lambda self: "no json here"})())
    assert main(["assess", "--stdin", "--backend", "fake"]) == 2
    assert not capsys.readouterr().out.strip()


def test_assess_stdin_envelope(monkeypatch, capsys):
    data = (FIXTURES / "benign.json").read_text(encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", type("S", (), {"read": lambda self: data})())
    rc = main(["assess", "--stdin", "--backend", "fake", "--policy", str(REPO / "policy" / "rules.json")])
    assert rc == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["action"] in {"proceed", "guide"}


def test_assess_envelope_contract_violation(tmp_path, capsys):
    bad = tmp_path / "bad-envelope.json"
    bad.write_text(json.dumps({"schema_version": "1"}), encoding="utf-8")
    assert main(["assess", "--input", str(bad), "--backend", "fake"]) == 2
    assert "malformed input" in capsys.readouterr().err


def test_assess_missing_policy(tmp_path, capsys):
    assert main([
        "assess", "--input", str(FIXTURES / "benign.json"), "--backend", "fake",
        "--policy", str(tmp_path / "nope.json"),
    ]) == 1
    assert "setup failed" in capsys.readouterr().err


def test_module_entrypoint_subprocess():
    if not SEED.exists():
        pytest.skip("corpus/seed.jsonl missing")
    proc = subprocess.run(
        [sys.executable, "-m", "patristic_ethics.cli", "corpus", "validate", str(SEED)],
        capture_output=True, text=True, cwd=str(REPO),
    )
    assert proc.returncode == 0
    assert "OK" in proc.stdout