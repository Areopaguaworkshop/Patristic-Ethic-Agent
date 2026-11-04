# Data and source rights

The **software** in this repository is licensed under the Apache License 2.0
(`LICENSE`). That licence does not relicense third-party texts, translations,
or bibliographic records.

## Corpus records

Every corpus record carries `rights_status` and `rights_evidence` fields. The
current seed contains:

- public-domain texts,
- CC-BY-4.0 texts,
- CC-BY-SA-4.0 texts.

The modern-government lane is marked `public-domain-unverified`. The scripture
lane is public domain. The secondary-reference pilot contains fair-use and
public-domain-unverified records. Further reading is **metadata only** and is
never quoted at runtime; it includes `library` and `unknown` rights records.

If you redistribute a corpus record, keep its attribution, licence, and
rights evidence. Do not relicense a third-party text merely because it is in
this repository. A derived database must preserve the applicable attribution
and share-alike terms.

## Excluded source files

Downloaded PDFs and other source files under `source/` are not part of the
public tree. They are ignored and must not be committed. The seed records are
the canonical data; `corpus/units.db` is a generated index.

## No warranty

The corpus contains draft and partially reviewed material. It is not a
complete critical edition, a statement of church teaching, or legal advice.
See `README.md` and the review records under `docs/` for the current limits.
