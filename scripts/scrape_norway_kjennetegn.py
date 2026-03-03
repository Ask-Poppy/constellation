#!/usr/bin/env python3
"""
Scrape Norwegian kjennetegn på måloppnåelse (assessment rubrics) from udir.no.

These are NOT in the GREP API — they exist only as HTML pages on udir.no.
Each page has consistent 3-column tables: grade 2 / grade 4 / grade 6.

Usage:
    python scripts/scrape_norway_kjennetegn.py              # Scrape all 10. trinn pages
    python scripts/scrape_norway_kjennetegn.py --all         # Scrape all pages including VGS
    python scripts/scrape_norway_kjennetegn.py --dry-run     # List pages without scraping
"""

import json
import re
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

BASE_URL = "https://www.udir.no"
INDEX_URL = f"{BASE_URL}/laring-og-trivsel/lareplanverket/kjennetegn/kjennetegn-pa-maloppnaelse-for-nye-lareplaner/"
OUTPUT_DIR = Path(__file__).parent.parent / "countries" / "norway" / "subjects"

PAGE_TO_SUBJECT = {
    "matematikk-10-trinn": ("mathematics", 10),
    "norsk-10.-trinn": ("norwegian", 10),
    "engelsk-10.-trinn": ("english", 10),
    "naturfag-10.-trinn": ("science", 10),
    "samfunnsfag-10-trinn": ("social-studies", 10),
    "krle-10.-trinn": ("religion-ethics", 10),
    "kunst-og-handverk-10.-trinn": ("arts-crafts", 10),
    "musikk-10.-trinn": ("music", 10),
    "kroppsoving-10.-trinn": ("physical-education", 10),
    "mat-og-helse-10.-trinn": ("food-health", 10),
    "arbeidslivsfag-pa-ungdomstrinnet": ("work-life-studies", 10),
    "fremmedsprak-niva-i": ("foreign-language", 10),
}


def extract_slug(path: str) -> str:
    base = "kjennetegn-pa-maloppnaelse"
    idx = path.rfind(base)
    if idx < 0:
        return ""
    remainder = path[idx + len(base):]
    return remainder.lstrip("-").rstrip("/")


def fetch_html(url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        try:
            time.sleep(0.3)
            req = Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; Poppy/1.0; curriculum-data)",
                "Accept": "text/html",
            })
            with urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except URLError as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt + 1}: {e}")
                time.sleep(2)
            else:
                print(f"  Failed: {url} — {e}")
                return ""


def clean_html(text: str) -> str:
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def parse_tables(html: str) -> list[dict]:
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.DOTALL)
    if not tables:
        return []

    table = tables[0]

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.DOTALL)
    if len(rows) < 2:
        return []

    criteria = []
    for row in rows[1:]:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 3:
            continue
        criteria.append({
            "low": clean_html(cells[0]),
            "medium": clean_html(cells[1]),
            "high": clean_html(cells[2]),
        })

    return criteria


def build_knowledge_criteria(criteria: list[dict]) -> list[dict]:
    if not criteria:
        return []

    low_texts = [c["low"] for c in criteria if c["low"]]
    medium_texts = [c["medium"] for c in criteria if c["medium"]]
    high_texts = [c["high"] for c in criteria if c["high"]]

    result = []
    if low_texts:
        result.append({
            "gradeStep": "2",
            "label": {"local": "Lav kompetanse, karakter 2", "en": "Low competency, grade 2"},
            "text": {"local": "\n".join(low_texts), "en": ""},
        })
    if medium_texts:
        result.append({
            "gradeStep": "4",
            "label": {"local": "God kompetanse, karakter 4", "en": "Good competency, grade 4"},
            "text": {"local": "\n".join(medium_texts), "en": ""},
        })
    if high_texts:
        result.append({
            "gradeStep": "6",
            "label": {"local": "Framifrå kompetanse, karakter 6", "en": "Excellent competency, grade 6"},
            "text": {"local": "\n".join(high_texts), "en": ""},
        })
    return result


def inject_into_subject(subject_file: str, after_grade: int, knowledge_criteria: list[dict]) -> bool:
    filepath = OUTPUT_DIR / f"{subject_file}.json"
    if not filepath.exists():
        print(f"  Subject file not found: {filepath}")
        return False

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = False
    for band in data["subject"]["gradeBands"]:
        if band["afterGrade"] == after_grade:
            band["knowledgeCriteria"] = knowledge_criteria
            updated = True
            break

    if not updated:
        print(f"  No grade band {after_grade} found in {subject_file}")
        return False

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return True


def discover_pages() -> list[str]:
    print("Fetching index page...")
    html = fetch_html(INDEX_URL)
    if not html:
        return []
    links = re.findall(
        r'href="(/laring-og-trivsel/lareplanverket/kjennetegn/kjennetegn-pa-maloppnaelse[^"]+)"',
        html,
    )
    index_path = "/laring-og-trivsel/lareplanverket/kjennetegn/kjennetegn-pa-maloppnaelse-for-nye-lareplaner/"
    return sorted(set(l for l in links if l != index_path))


def main():
    dry_run = "--dry-run" in sys.argv
    scrape_all = "--all" in sys.argv

    pages = discover_pages()
    print(f"Found {len(pages)} kjennetegn pages\n")

    if dry_run:
        for page in pages:
            slug = extract_slug(page)
            mapped = PAGE_TO_SUBJECT.get(slug, None)
            status = f"-> {mapped[0]} (grade {mapped[1]})" if mapped else "(not mapped)"
            print(f"  {slug} {status}")
        return

    scraped = 0
    for page in pages:
        slug = extract_slug(page)
        mapping = PAGE_TO_SUBJECT.get(slug)

        if not mapping:
            if not scrape_all:
                continue
            print(f"  Skipping unmapped: {slug}")
            continue

        subject_file, after_grade = mapping
        url = f"{BASE_URL}{page}"
        print(f"Scraping {slug}...")

        html = fetch_html(url)
        if not html:
            continue

        criteria = parse_tables(html)
        if not criteria:
            print(f"  No table data found")
            continue

        knowledge_criteria = build_knowledge_criteria(criteria)
        print(f"  {len(criteria)} dimensions, {len(knowledge_criteria)} grade levels")

        if inject_into_subject(subject_file, after_grade, knowledge_criteria):
            print(f"  Injected into {subject_file}.json (grade {after_grade})")
            scraped += 1

    print(f"\nDone. Scraped {scraped} pages.")


if __name__ == "__main__":
    main()
