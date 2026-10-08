from dataclasses import replace
from pathlib import Path

import pytest

from patristic_ethics.corpus import build_db, get_passage, load_seed, verify_quote
from patristic_ethics.tei_import import SOURCE_ID, import_sentences

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tests/fixtures/tei/greg_carmina.xml"


def selections():
    return [u for u in load_seed(ROOT / "corpus/seed.jsonl") if u.source_id == SOURCE_ID]


def test_actual_source_reproduces_seed_and_sqlite_metadata(tmp_path):
    import json
    from dataclasses import asdict

    templates = selections()
    imported = import_sentences(SOURCE, templates)
    assert imported == templates
    seed = tmp_path / "seed.jsonl"
    seed.write_text("".join(json.dumps(asdict(u), ensure_ascii=False) + "\n" for u in imported))
    db = build_db(seed, tmp_path / "corpus.db")
    for unit in imported:
        assert get_passage(db, unit.id) == unit
        assert verify_quote(db, unit.id, unit.text)


def test_changed_source_is_rejected(tmp_path):
    source = tmp_path / "source.xml"
    source.write_bytes(SOURCE.read_bytes().replace("δεινὸν".encode(), "ἀλλο".encode()))
    with pytest.raises(ValueError, match="source hash mismatch"):
        import_sentences(source, selections())


@pytest.mark.parametrize("change", [
    {"source_id": "other"}, {"locus": "sentence 20"},
    {"locus": "sentence 999"}, {"rights_status": "public-domain"},
])
def test_invalid_selection_is_rejected(change):
    with pytest.raises(ValueError):
        import_sentences(SOURCE, [replace(selections()[0], **change)])


def test_import_cannot_inherit_editorial_approval():
    unit = replace(selections()[0], review_status="reviewed")
    assert import_sentences(SOURCE, [unit])[0].review_status == "draft-unreviewed"


def test_pta_actual_source_reproduces_selected_span_and_metadata(tmp_path):
    import json
    from dataclasses import asdict
    from patristic_ethics.tei_import import PTA_ID, import_pta_sections

    templates = [u for u in load_seed(ROOT / "corpus/seed.jsonl") if u.source_id == PTA_ID]
    imported = import_pta_sections(ROOT / "tests/fixtures/tei/pta0022_grc1.xml", templates)
    assert imported == templates
    seed = tmp_path / "seed.jsonl"
    seed.write_text("".join(json.dumps(asdict(u), ensure_ascii=False) + "\n" for u in imported))
    db = build_db(seed, tmp_path / "corpus.db")
    assert get_passage(db, imported[0].id) == templates[0]
    assert verify_quote(db, imported[0].id, templates[0].text)


def test_lemma_extraction_excludes_variants_notes_and_preserves_tails():
    import xml.etree.ElementTree as ET
    from patristic_ethics.tei_import import _lemma_text

    node = ET.fromstring('''<p xmlns="http://www.tei-c.org/ns/1.0">Before <app type="variants"><lem>chosen <app type="variants"><lem/><rdg>added</rdg></app>word</lem><rdg>wrong</rdg></app> after<note>editorial</note> end<app type="witnesses"><rdg>other</rdg></app>.</p>''')
    assert _lemma_text(node) == "Before chosen word after end."
    for xml in ('<app><rdg>unselected</rdg></app>', '<app><lem>a</lem><lem>b</lem></app>', '<choice><orig>a</orig><reg>b</reg></choice>'):
        with pytest.raises(ValueError):
            _lemma_text(ET.fromstring(xml.replace('>', ' xmlns="http://www.tei-c.org/ns/1.0">', 1)))


@pytest.mark.parametrize("change", [{"locus": "section 999"}, {"text": "not in the edition"}, {"rights_status": "public-domain"}])
def test_pta_rejects_invalid_selection(change):
    from patristic_ethics.tei_import import PTA_ID, import_pta_sections
    template = next(u for u in load_seed(ROOT / "corpus/seed.jsonl") if u.source_id == PTA_ID)
    with pytest.raises(ValueError):
        import_pta_sections(ROOT / "tests/fixtures/tei/pta0022_grc1.xml", [replace(template, **change)])


@pytest.mark.parametrize("document", [2, 3, 9, 20, 300])
def test_syriac_actual_source_preserves_span_and_metadata(document, tmp_path):
    import json
    from dataclasses import asdict
    from patristic_ethics.tei_import import SYRIAC_IDS, import_syriac_sections

    templates = [u for u in load_seed(ROOT / "corpus/seed.jsonl")
                 if u.source_id in SYRIAC_IDS and u.source_url.endswith(f"/{document}.xml")]
    imported = import_syriac_sections(ROOT / f"tests/fixtures/tei/syr_{document}.xml", templates, document)
    assert imported == templates
    seed = tmp_path / "seed.jsonl"
    seed.write_text("".join(json.dumps(asdict(u), ensure_ascii=False) + "\n" for u in imported))
    db = build_db(seed, tmp_path / "corpus.db")
    for unit in imported:
        assert get_passage(db, unit.id) == unit
        assert verify_quote(db, unit.id, unit.text)


@pytest.mark.parametrize("change", [
    {"locus": "Demonstration 9 (On Humility), §2"},
    {"text": "ܐܠܗܐ fabricated"}, {"language": "en"},
    {"source_url": "https://example.test/9.xml"}, {"rights_status": "public-domain"},
])
def test_syriac_rejects_changed_selection(change):
    from patristic_ethics.tei_import import import_syriac_sections
    template = next(u for u in load_seed(ROOT / "corpus/seed.jsonl") if u.id == "u-syr-002")
    with pytest.raises(ValueError):
        import_syriac_sections(ROOT / "tests/fixtures/tei/syr_9.xml", [replace(template, **change)], 9)


def test_syriac_rejects_cross_document_and_preserves_draft_state():
    from patristic_ethics.tei_import import import_syriac_sections
    template = next(u for u in load_seed(ROOT / "corpus/seed.jsonl") if u.id == "u-syr-002")
    source = ROOT / "tests/fixtures/tei/syr_9.xml"
    with pytest.raises(ValueError, match="hash mismatch"):
        import_syriac_sections(source, [template], 2)
    assert import_syriac_sections(source, [replace(template, review_status="reviewed")], 9)[0].review_status == "draft-unreviewed"
