"""Offline, source-specific Greek TEI extraction; emits draft seed JSONL."""

import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .corpus import CorpusUnit, load_seed, sha256_text, validate_units

SOURCE_ID = "src-f1kg-tlg2022"
SOURCE_SHA256 = "54ef8223f6c559d1cdb9ab29435f26f47a95840a485a38ebfea59c1ecb17cf76"
URN = "urn:cts:greekLit:tlg2022.tlg060.1st1K-grc1"
SOURCE_URL = "https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/data/tlg2022/tlg060/tlg2022.tlg060.1st1K-grc1.xml"
NS = {"t": "http://www.tei-c.org/ns/1.0"}
PTA_ID = "src-pta-pta0022"
PTA_SHA256 = "fb1b4073a6727ffe8aa1f0ab462acf56dba7ce0b23b337ed3e2b7c14646ea2f5"
PTA_URN = "urn:cts:pta:pta0022.pta001.pta-grc1"
PTA_URL = "https://raw.githubusercontent.com/PatristicTextArchive/pta_data/master/data/pta0022/pta001/pta0022.pta001.pta-grc1.xml"
SYRIAC_IDS = ("src-syriac-corpus-aphrahat", "src-syriac-corpus-ephrem")
SYRIAC_HASHES = {
    2: "9049e08485b1747918e0eefabc1c96e7ca8f817d0beb0e05f6f53c2a56dd06df",
    3: "25a454cdaf7e98d16715dede044704757e7363e909580e41f99f9610401cf8e3",
    9: "7f616d532736e5f7e1a877a453661e7e402d66e2ef1ba95da8854fa7a6f0729e",
    20: "4a7957980498c3619a87a6f7e3e15b4cd3c3d7013cd98a74a4feef56c44a5ede",
    300: "f0c16726851e87b5427eacadcd5989a84ecba8665043f048f563b492c94c66a2",
}


def import_syriac_sections(source: str | Path, templates: list[CorpusUnit],
                           document: int) -> list[CorpusUnit]:
    """Extract exact spans from selected DSC prose paragraphs or hymn lines."""
    raw = Path(source).read_bytes()
    if document not in SYRIAC_HASHES or hashlib.sha256(raw).hexdigest() != SYRIAC_HASHES[document]:
        raise ValueError("unsupported document or source hash mismatch")
    root = ET.fromstring(raw)
    publication = root.find("./t:teiHeader/t:fileDesc/t:publicationStmt", NS)
    uri = publication.find("./t:idno[@type='URI']", NS)
    licence = publication.find("./t:availability/t:licence", NS)
    if (uri is None or uri.text != f"https://syriaccorpus.org/{document}"
            or licence is None or licence.get("target") != "http://creativecommons.org/licenses/by/4.0/"):
        raise ValueError("unexpected document identity or licence")
    url = f"https://raw.githubusercontent.com/srophe/syriac-corpus/master/data/tei/{document}.xml"
    source_id = SYRIAC_IDS[1] if document == 300 else SYRIAC_IDS[0]
    result = []
    for unit in templates:
        if (unit.source_id != source_id or unit.language != "syr"
                or unit.rights_status != "CC-BY-4.0" or unit.source_url != url
                or unit.rights_evidence != url or unit.cts_urn is not None):
            raise ValueError(f"{unit.id}: template does not match selected document")
        pattern = r"Nisibis 46, §([1-9][0-9]*)" if document == 300 else rf"Demonstration {document} \([^)]+\), §([1-9][0-9]*)"
        match = re.fullmatch(pattern, unit.locus or "")
        if not match or not isinstance(unit.text, str) or not unit.text.strip():
            raise ValueError(f"{unit.id}: paragraph locus and nonempty exact span required")
        prefix = "./t:text/t:body/t:div[@type='body']" if document == 300 else "./t:text/t:body"
        sections = root.findall(f"{prefix}/t:div[@type='section'][@n='{match[1]}']", NS)
        if len(sections) != 1:
            raise ValueError(f"{unit.id}: missing or duplicate section")
        section = sections[0]
        paragraphs = section.findall("./t:l" if document == 300 else "./t:p", NS)
        for p in paragraphs:
            language = p.get("{http://www.w3.org/XML/1998/namespace}lang", section.get("{http://www.w3.org/XML/1998/namespace}lang"))
            if language != "syr" or list(p):
                raise ValueError(f"{unit.id}: unsupported paragraph language or markup")
        section_text = " ".join(" ".join((p.text or "").split()) for p in paragraphs)
        span = " ".join(unit.text.split())
        if section_text.count(span) != 1:
            raise ValueError(f"{unit.id}: selected span is absent or ambiguous in section")
        start = section_text.index(span)
        text = section_text[start:start + len(span)]
        result.append(replace(unit, text=text, text_sha256=sha256_text(text),
                              retrieval_verified=True, review_status="draft-unreviewed",
                              offset_start=None, offset_end=None))
    problems = validate_units(result)
    if not result or problems:
        raise ValueError("invalid imported selection: " + "; ".join(problems))
    return result


def _lemma_text(node: ET.Element) -> str:
    """Read only edited text, preserving tails outside skipped apparatus."""
    tag = node.tag.removeprefix("{" + NS["t"] + "}")
    if tag in {"rdg", "note", "head", "pb", "lb"}:
        return ""
    if tag == "app":
        if node.get("type") == "witnesses":
            return ""
        lemmas = node.findall("./t:lem", NS)
        if len(lemmas) != 1:
            raise ValueError("variant apparatus must have exactly one edited lemma")
        return _lemma_text(lemmas[0])
    if tag not in {"div", "p", "lem", "persName", "orgName", "quote", "ref"}:
        raise ValueError(f"unsupported edited-text markup: {tag}")
    return (node.text or "") + "".join(_lemma_text(c) + (c.tail or "") for c in node)


def import_pta_sections(source: str | Path, templates: list[CorpusUnit]) -> list[CorpusUnit]:
    """Extract curated exact spans from the pinned PTA edition's lemma text."""
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PTA_SHA256:
        raise ValueError("source hash mismatch; review a changed edition before importing")
    root = ET.fromstring(raw)
    edition = root.find(f"./t:text/t:body/t:div[@n='{PTA_URN}']", NS)
    licence = root.find("./t:teiHeader/t:fileDesc/t:publicationStmt/t:availability/t:licence", NS)
    if (edition is None or edition.get("{http://www.w3.org/XML/1998/namespace}lang") != "grc"
            or licence is None or licence.get("target") != "https://creativecommons.org/licenses/by-sa/4.0/"):
        raise ValueError("unexpected edition identity, language, or licence")
    result = []
    for unit in templates:
        if (unit.source_id != PTA_ID or unit.cts_urn != PTA_URN or unit.language != "grc"
                or unit.rights_status != "CC-BY-SA-4.0"
                or unit.source_url != PTA_URL or unit.rights_evidence != PTA_URL):
            raise ValueError(f"{unit.id}: template does not match selected source")
        match = re.fullmatch(r"section ([1-9][0-9]*)", unit.locus or "")
        if not match or not isinstance(unit.text, str) or not unit.text.strip():
            raise ValueError(f"{unit.id}: section locus and nonempty exact span required")
        sections = edition.findall(f"./t:div[@subtype='section'][@n='{match[1]}']", NS)
        if len(sections) != 1:
            raise ValueError(f"{unit.id}: missing or duplicate section")
        section_text = " ".join(_lemma_text(sections[0]).split())
        span = " ".join(unit.text.split())
        if section_text.count(span) != 1:
            raise ValueError(f"{unit.id}: selected span is absent or ambiguous in edited section")
        start = section_text.index(span)
        text = section_text[start:start + len(span)]
        result.append(replace(unit, text=text, text_sha256=sha256_text(text),
                              retrieval_verified=True, review_status="draft-unreviewed",
                              offset_start=None, offset_end=None))
    problems = validate_units(result)
    if not result or problems:
        raise ValueError("invalid imported selection: " + "; ".join(problems))
    return result


def import_sentences(source: str | Path, templates: list[CorpusUnit]) -> list[CorpusUnit]:
    """Reproduce selected sentences from a hash-pinned, attributed edition.

    Editorial metadata comes from the curated seed, never inferred from XML.
    Importing does not grant editorial approval. No network access is performed.
    """
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("source hash mismatch; review a changed edition before importing")
    root = ET.fromstring(raw)
    edition = root.find(f"./t:text/t:body/t:div[@n='{URN}']", NS)
    licence = root.find("./t:teiHeader/t:fileDesc/t:publicationStmt/t:availability/t:licence", NS)
    if (edition is None or edition.get("{http://www.w3.org/XML/1998/namespace}lang") != "grc"
            or licence is None or licence.get("target") != "https://creativecommons.org/licenses/by-sa/4.0/"):
        raise ValueError("unexpected edition identity, language, or licence")
    result = []
    for unit in templates:
        if (unit.source_id != SOURCE_ID or unit.cts_urn != URN or unit.language != "grc"
                or unit.rights_status != "CC-BY-SA-4.0"
                or unit.source_url != SOURCE_URL or unit.rights_evidence != SOURCE_URL):
            raise ValueError(f"{unit.id}: template does not match selected source")
        match = re.fullmatch(r"sentence ([1-9][0-9]*)", unit.locus or "")
        if not match:
            raise ValueError(f"{unit.id}: unsupported sentence locus")
        nodes = edition.findall(f"./t:div[@subtype='sentence'][@n='{match[1]}']/t:p", NS)
        if len(nodes) != 1 or list(nodes[0]):
            raise ValueError(f"{unit.id}: missing, duplicate, or unsupported marked-up sentence")
        text = " ".join((nodes[0].text or "").split())
        result.append(replace(unit, text=text, text_sha256=sha256_text(text),
                              retrieval_verified=True, review_status="draft-unreviewed",
                              offset_start=None, offset_end=None))
    problems = validate_units(result)
    if not result or problems:
        raise ValueError("invalid imported selection: " + "; ".join(problems))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("seed", type=Path, help="curated metadata and sentence selections")
    parser.add_argument("--source-id", choices=[SOURCE_ID, PTA_ID, *SYRIAC_IDS], default=SOURCE_ID)
    parser.add_argument("--document", type=int, choices=SYRIAC_HASHES)
    args = parser.parse_args()
    templates = [u for u in load_seed(args.seed) if u.source_id == args.source_id]
    try:
        if args.source_id in SYRIAC_IDS:
            if args.document is None:
                parser.error("--document is required for Syriac sources")
            templates = [u for u in templates if u.source_url.endswith(f"/{args.document}.xml")]
            units = import_syriac_sections(args.source, templates, args.document)
        else:
            if args.document is not None:
                parser.error("--document applies only to Syriac sources")
            importer = import_sentences if args.source_id == SOURCE_ID else import_pta_sections
            units = importer(args.source, templates)
    except ValueError as exc:
        parser.error(str(exc))
    for unit in units:
        print(json.dumps(asdict(unit), ensure_ascii=False))


if __name__ == "__main__":
    main()
