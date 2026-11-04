"""CSL-JSON citation lanes for modern and scripture sources."""

from pathlib import Path

import pytest

from patristic_ethics import csl
from patristic_ethics.guidance import _citations_from

ROOT = Path(__file__).resolve().parents[1]
MODERN = ROOT / "corpus" / "modern.jsonl"
SCRIPTURE = ROOT / "corpus" / "scripture.jsonl"


def test_real_lanes_validate():
    assert csl.validate_csl(csl.load_csl(MODERN), "modern") == []
    assert csl.validate_csl(csl.load_csl(SCRIPTURE), "scripture") == []


def test_modern_lane_build_search_and_verify(tmp_path):
    records = csl.load_csl(MODERN)
    db = csl.build_csl_db(records, tmp_path / "modern.db", "modern")
    hits = csl.search_csl(db, "terrorists", 5)
    assert hits and hits[0].source_class == "modern_government"
    unit = csl.get_csl_unit(db, "us-wh-nsct-2018-p01")
    assert unit is not None
    assert unit.citation_index == "US-WH-NSCT-2018"
    assert csl.verify_csl_quote(db, unit.id, "We must defeat the terrorists")
    assert not csl.verify_csl_quote(db, unit.id, "fabricated quotation")


def test_scripture_lane_build_and_verify(tmp_path):
    records = csl.load_csl(SCRIPTURE)
    db = csl.build_csl_db(records, tmp_path / "scripture.db", "scripture")
    unit = csl.get_csl_unit(db, "kjv-matt-5-9")
    assert unit is not None
    assert unit.source_class == "scripture"
    assert csl.verify_csl_quote(db, unit.id, "Blessed are the peacemakers")


def test_csl_unit_feeds_runtime_citation_label(tmp_path):
    records = csl.load_csl(MODERN)
    db = csl.build_csl_db(records, tmp_path / "modern.db", "modern")
    unit = csl.get_csl_unit(db, records[0]["id"])
    citation = _citations_from([unit])[0]
    assert citation.source_class == "modern_government"
    assert citation.unit_id == records[0]["id"]


def test_lanes_do_not_mix(tmp_path):
    modern_db = csl.build_csl_db(csl.load_csl(MODERN), tmp_path / "modern.db", "modern")
    scripture_db = csl.build_csl_db(
        csl.load_csl(SCRIPTURE), tmp_path / "scripture.db", "scripture"
    )
    assert csl.search_csl(modern_db, "peacemakers", 5) == []
    assert csl.search_csl(scripture_db, "counterterrorism", 5) == []


def test_validation_rejects_lane_and_hash_errors():
    record = csl.load_csl(MODERN)[0]
    record["custom"]["source_class"] = "scripture"
    assert any("does not match lane" in p for p in csl.validate_csl([record], "modern"))

    record = csl.load_csl(SCRIPTURE)[0]
    record["custom"]["text"] = record["custom"]["text"] + " altered"
    assert any("text_sha256" in p for p in csl.validate_csl([record], "scripture"))


def test_build_rejects_invalid_records(tmp_path):
    record = csl.load_csl(MODERN)[0]
    record["custom"]["text_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        csl.build_csl_db([record], tmp_path / "bad.db", "modern")
