#!/usr/bin/env python3
"""Re-verify further-reading records against CiteIndex-style evidence rules.

- DOI records: exact Crossref lookup; compare title, authors, year.
- Google Scholar / preview search URLs: mark as lead-only.
- Other URLs: fetch page metadata and compare the title.
- Never overwrite bibliographic fields; record verification state and evidence.

This is a registry/URL check, not owner review and not proof of source authority.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "corpus" / "further_reading.jsonl"
REPORT = ROOT / "docs" / "research" / "2026-10-23-further-reading-verification.md"
UA = "PEA-bibliography-verifier/0.1"
LEAD_HOSTS = (
    "scholar.google.com",
    "books.google.com",
    "search.proquest.com",
    "search.ebscohost.com",
)


def norm_title(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"&", " and ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def titles_match(left: str, right: str) -> bool:
    a, b = norm_title(left), norm_title(right)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.90


def family_names(names) -> list[str]:
    out = []
    for person in names or []:
        if not isinstance(person, dict):
            continue
        name = person.get("family") or person.get("literal") or ""
        if name:
            out.append(str(name).casefold())
    return out


def year_of(record: dict) -> int | None:
    parts = (record.get("issued") or {}).get("date-parts") or []
    if parts and parts[0] and isinstance(parts[0][0], int):
        return parts[0][0]
    return None


def crossref(doi: str) -> dict:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def verify_doi(record: dict) -> tuple[str, str, str]:
    doi = str(record.get("DOI") or "").strip()
    try:
        payload = crossref(doi)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "crossref-not-found", "https://doi.org/" + doi, "Crossref has no record for this DOI."
        return "crossref-error", "https://doi.org/" + doi, f"Crossref HTTP {exc.code}."
    except Exception as exc:
        return "crossref-error", "https://doi.org/" + doi, f"Crossref request failed: {type(exc).__name__}."
    message = payload.get("message") or {}
    crossref_titles = message.get("title") or []
    crossref_title = crossref_titles[0] if crossref_titles else ""
    crossref_year = None
    parts = (message.get("issued") or {}).get("date-parts") or []
    if parts and parts[0] and isinstance(parts[0][0], int):
        crossref_year = parts[0][0]
    title_ok = titles_match(str(record.get("title") or ""), crossref_title)
    year_ok = year_of(record) == crossref_year
    local_authors = set(family_names(record.get("author") or record.get("editor")))
    remote_authors = set(family_names(message.get("author") or message.get("editor")))
    author_ok = bool(local_authors & remote_authors) if local_authors and remote_authors else True
    notes = []
    if not title_ok:
        notes.append(f"title differs: local {record.get('title')!r}; Crossref {crossref_title!r}")
    if not year_ok:
        notes.append(f"year differs: local {year_of(record)}; Crossref {crossref_year}")
    if not author_ok:
        notes.append(f"author family differs: local {sorted(local_authors)}; Crossref {sorted(remote_authors)}")
    if title_ok and year_ok and author_ok:
        return "crossref-match", "https://doi.org/" + doi, "Crossref title, year, and author agree."
    if title_ok or year_ok or author_ok:
        return "crossref-partial", "https://doi.org/" + doi, "; ".join(notes)
    return "crossref-mismatch", "https://doi.org/" + doi, "; ".join(notes)


def meta(html: str, name: str) -> str | None:
    patterns = [
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(name)}["\']',
        rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',
    ]
    for pattern in patterns:
        found = re.search(pattern, html, flags=re.I)
        if found:
            return found.group(1)
    return None


def fetch_title(url: str) -> tuple[str | None, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as response:
        ctype = response.headers.get("Content-Type", "")
        if "pdf" in ctype.casefold():
            return None, "PDF source; no HTML metadata check."
        raw = response.read(350_000)
    html = raw.decode("utf-8", errors="replace")
    title = (
        meta(html, "citation_title")
        or meta(html, "dc.title")
        or meta(html, "og:title")
        or (re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.S | re.I) or [None, None])[1]
    )
    if title:
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title)).strip()
    return title, None


def verify_url(record: dict) -> tuple[str, str, str]:
    url = str(record.get("URL") or "").strip()
    if "scholar.google.com" in url:
        return "lead-only", url, "Google Scholar search URL; not a stable source record."
    host = urllib.parse.urlparse(url).netloc.casefold()
    if any(host == lead or host.endswith("." + lead) for lead in LEAD_HOSTS):
        return "lead-only", url, "Search/preview URL; not a stable source record."
    try:
        title, reason = fetch_title(url)
    except urllib.error.HTTPError as exc:
        return "url-unreachable", url, f"HTTP {exc.code}."
    except Exception as exc:
        return "url-unreachable", url, f"Fetch failed: {type(exc).__name__}."
    if title is None:
        return "url-no-metadata", url, reason or "No title metadata found."
    if titles_match(str(record.get("title") or ""), title):
        return "url-match", url, f"Page title agrees: {title!r}."
    return "url-mismatch", url, f"Page title differs: local {record.get('title')!r}; page {title!r}."


def main() -> int:
    records = []
    for line in PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    counts: dict[str, int] = {}
    problems = []
    for index, record in enumerate(records, start=1):
        custom = record.setdefault("custom", {})
        if record.get("DOI"):
            status, evidence, note = verify_doi(record)
            time.sleep(1.0)
        elif record.get("URL"):
            status, evidence, note = verify_url(record)
            time.sleep(0.5)
        else:
            status, evidence, note = "needs-review", "", "No DOI or URL."
        custom["verification_status"] = status
        custom["verification_evidence"] = evidence
        custom["verification_source"] = (
            "crossref" if status.startswith("crossref")
            else "url-metadata" if status.startswith("url")
            else "none"
        )
        custom["verified_at"] = "2026-10-23"
        custom["verification_notes"] = note
        counts[status] = counts.get(status, 0) + 1
        if status not in {"crossref-match", "url-match", "lead-only"}:
            problems.append((record.get("id", f"#{index}"), status, note))
        if index % 10 == 0:
            print(f"checked {index}/{len(records)}", file=sys.stderr)
    PATH.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=False) for r in records) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Further-reading verification — 2026-10-23",
        "",
        "Registry and URL-metadata pass following CiteIndex evidence rules. This is not owner review.",
        "",
        "## Counts",
        "",
        "| Status | Count |",
        "|---|---|",
    ]
    for status in sorted(counts):
        lines.append(f"| {status} | {counts[status]} |")
    lines += ["", "## Needs review", ""]
    if problems:
        for uid, status, note in problems:
            lines.append(f"- `{uid}` — {status}: {note}")
    else:
        lines.append("None.")
    lines += [
        "",
        "## Limits",
        "",
        "- Crossref agreement is registry evidence, not a source-title-page check.",
        "- Google Scholar and search/preview URLs are leads, not stable records.",
        "- URL title checks do not verify authors, dates, publishers, or rights.",
        "- No bibliographic field was overwritten.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(counts, indent=2))
    print(f"wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
