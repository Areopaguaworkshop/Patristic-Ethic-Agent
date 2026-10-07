"""Offline tests for the seed corpus module (plan M1b): load/validate,
hash checking, SQLite FTS5 build/search, and quote fidelity."""

import json

import pytest

from patristic_ethics.corpus import (
    CorpusUnit,
    build_db,
    get_passage,
    load_seed,
    search_passages,
    sha256_text,
    validate_units,
    verify_quote,
)

THEFT = "Theft is punished by Thy law, O Lord, and by the law written in men’s hearts."


def unit(**over):
    """Minimal valid unit; override per test."""
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
        "text": THEFT,
        "text_sha256": sha256_text(THEFT),
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


def test_load_seed_roundtrip(tmp_path):
    path = write_seed(tmp_path, [unit(), unit(id="u-test-002")])
    units = load_seed(path)
    assert len(units) == 2
    assert units[0].id == "u-test-001"
    assert units[1].text == THEFT
    assert units[0].principle_ids == ["PEA-P01"]


def test_load_seed_malformed_line(tmp_path):
    path = tmp_path / "seed.jsonl"
    path.write_text(json.dumps(unit()) + "\nnot json at all\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"seed[.]jsonl:2: malformed JSON"):
        load_seed(path)


def test_load_seed_missing_field(tmp_path):
    path = tmp_path / "seed.jsonl"
    bad = unit()
    del bad["author"]
    path.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="author"):
        load_seed(path)


def as_units(*overrides):
    return [CorpusUnit.from_json(unit(**o)) for o in overrides]


def test_validate_clean_units_pass():
    problems = validate_units(as_units({}, {"id": "u-test-002"}))
    assert problems == []


def test_validate_duplicate_id_detected():
    problems = validate_units(as_units({}, {}))
    assert any("duplicate id" in p for p in problems)


def test_validate_hash_mismatch_detected():
    problems = validate_units(as_units({"text_sha256": "deadbeef"}))
    assert any("text_sha256" in p and "match" in p for p in problems)


def test_validate_text_without_hash():
    problems = validate_units(as_units({"text_sha256": None}))
    assert any("text_sha256 missing" in p for p in problems)


def test_validate_missing_author_and_source_url():
    problems = validate_units(as_units({"author": "", "source_url": ""}))
    assert any("missing author" in p for p in problems)
    assert any("missing source_url" in p for p in problems)


def test_validate_verified_with_null_text():
    problems = validate_units(as_units({"text": None, "text_sha256": None}))
    assert any("text is null" in p for p in problems)


def test_build_db_and_fts_search(tmp_path):
    seed = write_seed(
        tmp_path,
        [
            unit(),
            unit(id="u-test-002", text="Wrath is the root of murder.", text_sha256=sha256_text("Wrath is the root of murder.")),
        ],
    )
    db = build_db(seed, tmp_path / "corpus.db")
    assert db.exists()

    hits = search_passages(db, "wrath")
    assert hits and hits[0].id == "u-test-002"
    assert hits[0].text is not None and "wrath" in hits[0].text.lower()

    # author field is searchable too
    by_author = search_passages(db, "Test")
    assert len(by_author) == 2


def test_search_limit_and_null_text_rows(tmp_path):
    seed = write_seed(
        tmp_path,
        [
            unit(),
            unit(id="u-test-002", text=None, text_sha256=None, retrieval_verified=False),
        ],
    )
    db = build_db(seed, tmp_path / "corpus.db")
    hits = search_passages(db, "theft", limit=1)
    assert len(hits) == 1 and hits[0].id == "u-test-001"


def test_get_passage(tmp_path):
    seed = write_seed(tmp_path, [unit()])
    db = build_db(seed, tmp_path / "corpus.db")
    got = get_passage(db, "u-test-001")
    assert got is not None and got.author == "Test Author"
    assert get_passage(db, "no-such-id") is None


def test_verify_quote_fidelity(tmp_path):
    seed = write_seed(tmp_path, [unit()])
    db = build_db(seed, tmp_path / "corpus.db")
    # exact span
    assert verify_quote(db, "u-test-001", THEFT) is True
    # substring of stored text
    assert verify_quote(db, "u-test-001", "Theft is punished by Thy law") is True
    # altered words must fail (no fuzzy matching)
    assert verify_quote(db, "u-test-001", THEFT.replace("Theft", "Robbery")) is False
    assert verify_quote(db, "u-test-001", THEFT.upper()) is False
    # whitespace collapse: newlines/extra spaces in the quote still match
    assert verify_quote(db, "u-test-001", "  ".join(THEFT.split())) is True
    assert verify_quote(db, "u-test-001", THEFT.replace(" ", "\n")) is True
    # unknown id
    assert verify_quote(db, "no-such-id", THEFT) is False


def test_build_db_deterministic(tmp_path):
    seed = write_seed(tmp_path, [unit(), unit(id="u-test-002")])
    db1 = build_db(seed, tmp_path / "corpus.db")
    n1 = len(search_passages(db1, "Test", limit=100))
    db2 = build_db(seed, tmp_path / "corpus.db")
    n2 = len(search_passages(db2, "Test", limit=100))
    assert db1 == db2
    assert n1 == n2 == 2


def test_build_db_rejects_problems(tmp_path):
    seed = write_seed(tmp_path, [unit(), unit()])  # duplicate id
    with pytest.raises(ValueError, match="duplicate id"):
        build_db(seed, tmp_path / "corpus.db")