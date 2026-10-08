# Selected TEI fixture

`greg_carmina.xml` is an unchanged cached copy of [First1KGreek tlg2022.tlg060.1st1K-grc1](https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/data/tlg2022/tlg060/tlg2022.tlg060.1st1K-grc1.xml), retrieved 2026-10-06. Its full attribution and edition header is retained: pseudo-Menander/Gregory Nazianzus attribution, Manfred Ullmann edition (1961), electronic edition University of Leipzig and Digital Corpus for Graeco-Arabic Studies, with contributors named in the header.

The XML is distributed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); this licence applies to the fixture and its extracted text. The fixture has not been modified. Its SHA-256 is `54ef8223f6c559d1cdb9ab29435f26f47a95840a485a38ebfea59c1ecb17cf76`. No English translation is supplied.

## Reproduce the four existing selections

```sh
PYTHONPATH=src .venv/bin/python -m patristic_ethics.tei_import tests/fixtures/tei/greg_carmina.xml corpus/seed.jsonl > /tmp/pea-tei-import.jsonl
PYTHONPATH=src .venv/bin/python -m patristic_ethics.cli corpus validate /tmp/pea-tei-import.jsonl
```

Output contains only the selected First1KGreek units, not the entire multilingual seed. The original corpus is not overwritten. The importer preserves curated metadata, extracts sentence numbers 4/7/8/22, calculates text hashes, and resets review state to draft-unreviewed. A changed XML digest requires an explicit code/source review before updating the pinned hash. This proves reproducibility against the pinned fixture; it does not independently establish authenticity of a newly downloaded upstream file.

Support is limited to this edition's plain paragraph sentences. Empty sentence 20, missing selections, unsupported markup, wrong source identity or licence claims are rejected. PTA apparatus and Digital Syriac Corpus structures need their own import checks; neither is claimed supported by this importer.

## PTA apparatus fixture

`pta0022_grc1.xml` is the unchanged cached [PTA Contra gentes Greek edition](https://raw.githubusercontent.com/PatristicTextArchive/pta_data/master/data/pta0022/pta001/pta0022.pta001.pta-grc1.xml), retrieved 2026-10-06, SHA-256 `fb1b4073a6727ffe8aa1f0ab462acf56dba7ce0b23b337ed3e2b7c14646ea2f5`. The retained header names Athanasius Alexandrinus, editor Kyriakos Savvidis, distributor Patristic Text Archive and authority Patristische Arbeitsstelle Bochum (2018). The XML and extracted text are under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The fixture has not been modified.

```sh
PYTHONPATH=src .venv/bin/python -m patristic_ethics.tei_import tests/fixtures/tei/pta0022_grc1.xml corpus/seed.jsonl --source-id src-pta-pta0022 > /tmp/pea-pta-import.jsonl
PYTHONPATH=src .venv/bin/python -m patristic_ethics.cli corpus validate /tmp/pea-pta-import.jsonl
```

The curated template supplies the exact excerpt selection and section locus. The importer reconstructs the section using only edited lemmas, finds exactly one matching span, and extracts it. It excludes manuscript readings, witness-only apparatus and notes, preserving surrounding text and punctuation. Missing or multiple edited lemmas and unsupported edited markup fail closed. This is a source-specific extraction tool, not a general TEI renderer. Import does not approve the theological mapping.

## Digital Syriac Corpus fixtures

Five unchanged cached TEI files, retrieved 2026-10-06, cover Aphrahat Demonstrations 2, 3, 9 and 20 and Ephrem Nisibis 46 (document 300). Original edition, responsibility, source-description and licence headers are retained. Attribution: Digital Syriac Corpus; James E. Walters and contributors identified in each file's header. The electronic editions and fixtures are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). No new translation is supplied. This licence statement concerns the electronic editions; it is not an independent determination of every base edition's copyright status.

| Fixture | Original source | SHA-256 |
|---|---|---|
| `syr_2.xml` | [DSC 2](https://raw.githubusercontent.com/srophe/syriac-corpus/master/data/tei/2.xml) | `9049e08485b1747918e0eefabc1c96e7ca8f817d0beb0e05f6f53c2a56dd06df` |
| `syr_3.xml` | [DSC 3](https://raw.githubusercontent.com/srophe/syriac-corpus/master/data/tei/3.xml) | `25a454cdaf7e98d16715dede044704757e7363e909580e41f99f9610401cf8e3` |
| `syr_9.xml` | [DSC 9](https://raw.githubusercontent.com/srophe/syriac-corpus/master/data/tei/9.xml) | `7f616d532736e5f7e1a877a453661e7e402d66e2ef1ba95da8854fa7a6f0729e` |
| `syr_20.xml` | [DSC 20](https://raw.githubusercontent.com/srophe/syriac-corpus/master/data/tei/20.xml) | `4a7957980498c3619a87a6f7e3e15b4cd3c3d7013cd98a74a4feef56c44a5ede` |
| `syr_300.xml` | [DSC 300](https://raw.githubusercontent.com/srophe/syriac-corpus/master/data/tei/300.xml) | `f0c16726851e87b5427eacadcd5989a84ecba8665043f048f563b492c94c66a2` |

Example reproduction:

```sh
PYTHONPATH=src .venv/bin/python -m patristic_ethics.tei_import tests/fixtures/tei/syr_9.xml corpus/seed.jsonl --source-id src-syriac-corpus-aphrahat --document 9 > /tmp/pea-syriac-import.jsonl
PYTHONPATH=src .venv/bin/python -m patristic_ethics.cli corpus validate /tmp/pea-syriac-import.jsonl
```

For document 300, use `--source-id src-syriac-corpus-ephrem --document 300`. Prose extracts only Syriac paragraphs from the specified section; hymns join Syriac verse lines in order. Editorial section headings are excluded. Exact curated excerpts must occur once in the selected section. Unicode characters, combining marks and punctuation are retained; only whitespace is collapsed. Unsupported inline markup is rejected rather than silently flattened. The importer binds document number, source URL, rights evidence, header URI, licence and file digest; output remains draft-unreviewed.
