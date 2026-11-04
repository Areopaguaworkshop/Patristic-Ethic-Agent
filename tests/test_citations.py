"""Primary and secondary CSL citation records."""

from pathlib import Path
from collections import Counter

from patristic_ethics import citations, corpus

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "corpus" / "seed.jsonl"
PRIMARY = ROOT / "corpus" / "primary_citations.jsonl"
SECONDARY = ROOT / "corpus" / "secondary.jsonl"


def _seed():
    return {unit.id: unit for unit in corpus.load_seed(SEED)}


def test_primary_citations_validate():
    records = citations.load_primary_citations(PRIMARY)
    assert len(records) == 33
    assert citations.validate_primary_citations(records, _seed()) == []


def test_secondary_records_validate():
    records = citations.load_secondary(SECONDARY)
    assert len(records) == 8
    assert citations.validate_secondary(records, set(_seed())) == []


def test_every_reviewed_unit_has_two_secondary_links():
    units = _seed()
    records = citations.load_secondary(SECONDARY)
    counts = Counter(
        uid
        for record in records
        for uid in record["custom"]["linked_unit_ids"]
    )
    reviewed = {uid for uid, unit in units.items() if unit.review_status == "reviewed"}
    assert reviewed
    assert all(counts[uid] >= 2 for uid in reviewed), {
        uid: counts[uid] for uid in sorted(reviewed) if counts[uid] < 2
    }


def test_secondary_unknown_unit_is_rejected():
    records = citations.load_secondary(SECONDARY)
    records[0]["custom"]["linked_unit_ids"] = ["u-grc-999"]
    assert any("unknown unit" in p for p in citations.validate_secondary(records, set(_seed())))


def test_secondary_quote_hash_is_checked():
    records = citations.load_secondary(SECONDARY)
    records[0]["custom"]["quote"] += " altered"
    assert any("quote_sha256" in p for p in citations.validate_secondary(records, set(_seed())))


def test_primary_citation_hash_is_checked():
    units = _seed()
    records = citations.load_primary_citations(PRIMARY)
    records[0]["custom"]["unit_text_sha256"] = "0" * 64
    assert any("unit_text_sha256" in p for p in citations.validate_primary_citations(records, units))
