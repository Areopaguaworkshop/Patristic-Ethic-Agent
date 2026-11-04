"""Linked CSL provenance records for corpus units."""

from pathlib import Path

from patristic_ethics import corpus, provenance

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "corpus" / "seed.jsonl"
PROV = ROOT / "corpus" / "provenance.jsonl"


def test_real_provenance_links_validate():
    known = {unit.id for unit in corpus.load_seed(SEED)}
    records = provenance.load_provenance(PROV)
    assert provenance.validate_provenance(records, known) == []


def test_unknown_unit_is_rejected():
    known = {unit.id for unit in corpus.load_seed(SEED)}
    records = provenance.load_provenance(PROV)
    records[0]["custom"]["linked_unit_ids"] = ["u-grc-999"]
    assert any("unknown unit" in p for p in provenance.validate_provenance(records, known))


def test_missing_role_is_rejected():
    known = {unit.id for unit in corpus.load_seed(SEED)}
    records = provenance.load_provenance(PROV)
    records[0]["custom"]["provenance_role"] = "maybe"
    assert any("provenance_role" in p for p in provenance.validate_provenance(records, known))


def test_missing_author_and_editor_is_rejected():
    known = {unit.id for unit in corpus.load_seed(SEED)}
    records = provenance.load_provenance(PROV)
    records[0].pop("author", None)
    assert any("author or editor" in p for p in provenance.validate_provenance(records, known))
