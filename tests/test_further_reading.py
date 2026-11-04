"""Further-reading bibliography validation and display."""

from pathlib import Path

import pytest

from patristic_ethics import corpus, further_reading

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "corpus" / "further_reading.example.jsonl"
SEED = ROOT / "corpus" / "seed.jsonl"


def _known():
    return {unit.id for unit in corpus.load_seed(SEED)}


def test_example_validates():
    records = further_reading.load_further_reading(EXAMPLE)
    assert len(records) == 1
    assert further_reading.validate_further_reading(records, _known()) == []


def test_quote_is_rejected():
    records = further_reading.load_further_reading(EXAMPLE)
    records[0]["custom"]["quote"] = "secondary quotation"
    assert any("must not contain a quotation" in p for p in further_reading.validate_further_reading(records, _known()))


def test_unknown_principle_is_rejected():
    records = further_reading.load_further_reading(EXAMPLE)
    records[0]["custom"]["principle_ids"] = ["PEA-P11"]
    assert any("unknown principle" in p for p in further_reading.validate_further_reading(records, _known()))


def test_unknown_linked_unit_is_rejected():
    records = further_reading.load_further_reading(EXAMPLE)
    records[0]["custom"]["linked_unit_ids"] = ["u-grc-999"]
    assert any("unknown unit" in p for p in further_reading.validate_further_reading(records, _known()))


def test_group_and_markdown():
    records = further_reading.load_further_reading(EXAMPLE)
    grouped = further_reading.group_by_principle(records)
    assert "PEA-P01" in grouped
    text = further_reading.render_markdown(records)
    assert "Further reading by principle" in text
    assert "Example further-reading record" in text
    assert "PEA-P01" in text


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        further_reading.load_further_reading(ROOT / "corpus" / "no-such-file.jsonl")
