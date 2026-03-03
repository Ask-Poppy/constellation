#!/usr/bin/env python3
"""
Sync Swedish Lgr22 curriculum data from Skolverket's Syllabus API.

Usage:
    python scripts/sync_sweden.py                  # Fetch all subjects
    python scripts/sync_sweden.py GRGRMAT01        # Fetch single subject
    python scripts/sync_sweden.py --list           # List available subjects

API docs: https://api.skolverket.se/syllabus/swagger-ui/index.html
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

BASE_URL = "https://api.skolverket.se/syllabus/v1"
OUTPUT_DIR = Path(__file__).parent.parent / "countries" / "sweden" / "subjects"
METADATA_PATH = Path(__file__).parent.parent / "countries" / "sweden" / "metadata.json"

SUBJECTS = {
    "GRGRMAT01": "mathematics",
    "GRGRSVE01": "swedish",
    "GRGRENG01": "english",
    "GRGRBIO01": "biology",
    "GRGRFYS01": "physics",
    "GRGRKEM01": "chemistry",
    "GRGRGEO01": "geography",
    "GRGRHIS01": "history",
    "GRGRSAM01": "social-studies",
    "GRGRREL01": "religion",
    "GRGRBIL01": "arts",
    "GRGRMUS01": "music",
    "GRGRIDR01": "physical-education",
    "GRGRHKK01": "home-economics",
    "GRGRSLJ01": "crafts",
    "GRGRTEK01": "technology",
    "GRGRMSP01": "modern-languages",
    "GRGRSVA01": "swedish-second-language",
    "GRGRMOD01": "mother-tongue",
    "GRGRTSP01": "sign-language",
}

ENGLISH_NAMES = {
    "GRGRMAT01": "Mathematics",
    "GRGRSVE01": "Swedish",
    "GRGRENG01": "English",
    "GRGRBIO01": "Biology",
    "GRGRFYS01": "Physics",
    "GRGRKEM01": "Chemistry",
    "GRGRGEO01": "Geography",
    "GRGRHIS01": "History",
    "GRGRSAM01": "Social Studies",
    "GRGRREL01": "Religion",
    "GRGRBIL01": "Arts",
    "GRGRMUS01": "Music",
    "GRGRIDR01": "Physical Education and Health",
    "GRGRHKK01": "Home and Consumer Studies",
    "GRGRSLJ01": "Crafts",
    "GRGRTEK01": "Technology",
    "GRGRMSP01": "Modern Languages",
    "GRGRSVA01": "Swedish as a Second Language",
    "GRGRMOD01": "Mother Tongue",
    "GRGRTSP01": "Sign Language for the Hearing",
}

GRADE_BAND_LABELS_EN = {
    "1-3": "Years 1-3",
    "4-6": "Years 4-6",
    "7-9": "Years 7-9",
    "1-6": "Years 1-6",
    "4-9": "Years 4-9",
}

GRADE_BAND_AFTER_GRADE = {
    "1-3": 3,
    "4-6": 6,
    "7-9": 9,
    "1-6": 6,
    "4-9": 9,
}


class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            self.result.append(data)

    def get_text(self):
        return "".join(self.result).strip()


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def extract_bullet_points(html: str) -> list[str]:
    items = re.findall(r"<li>(.*?)</li>", html, re.DOTALL)
    return [strip_html(item).strip() for item in items if strip_html(item).strip()]


def extract_central_content_sections(html: str) -> list[dict]:
    sections = []
    parts = re.split(r"<h4>(.*?)</h4>", html)

    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            heading = strip_html(parts[i]).strip()
            body = parts[i + 1] if i + 1 < len(parts) else ""
            items = extract_bullet_points(body)
            if items:
                sections.append({"heading": heading, "items": items})
    else:
        items = extract_bullet_points(html)
        if items:
            sections.append({"heading": "", "items": items})

    return sections


def fetch_json(url: str, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            time.sleep(0.3)
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError) as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt + 1}: {e}")
                time.sleep(2)
            else:
                print(f"  Failed: {url} — {e}")
                return None


def parse_year_range(year_str: str) -> int | None:
    return GRADE_BAND_AFTER_GRADE.get(year_str)


def extract_description(purpose_html: str) -> str:
    parts = purpose_html.split("<ul>")
    intro = parts[0] if parts else ""
    text = strip_html(intro).replace("\u00ad", "")
    return text


def extract_purpose_aims(purpose_html: str) -> list[str]:
    items = extract_bullet_points(purpose_html)
    return items


def extract_verbs(text: str) -> list[str]:
    verb_patterns = [
        "använda", "analysera", "argumentera", "bedöma", "beräkna",
        "beskriva", "bearbeta", "formulera", "föra", "förklara",
        "förstå", "gestalta", "granska", "hantera", "jämföra",
        "kommunicera", "lösa", "planera", "presentera", "pröva",
        "reflektera", "resonera", "samtala", "skapa", "söka",
        "tolka", "undersöka", "uttrycka", "utvärdera", "utveckla",
        "värdera", "välja", "visa",
    ]
    found = []
    text_lower = text.lower()
    for verb in verb_patterns:
        if verb in text_lower:
            found.append(verb.capitalize())
    return found


def sync_subject(code: str, filename: str) -> dict | None:
    print(f"\nFetching {code} ({ENGLISH_NAMES.get(code, filename)})...")

    data = fetch_json(f"{BASE_URL}/subjects/{code}")
    if not data:
        return None

    subject = data.get("subject") or data
    if "subject" in data and isinstance(data["subject"], dict):
        subject = data["subject"]

    subject_name = subject.get("name", code)
    subject_code = subject.get("code", code)
    designation = subject.get("designation", "")

    central_contents = subject.get("centralContents", [])
    knowledge_reqs = subject.get("knowledgeRequirements", [])
    purpose_html = subject.get("purpose", "")

    description_local = extract_description(purpose_html)
    purpose_aims = extract_purpose_aims(purpose_html)

    core_elements = []
    for aim in purpose_aims:
        core_elements.append({
            "code": "",
            "name": {"local": aim, "en": ""},
            "description": {"local": aim, "en": ""},
        })

    grade_bands = []
    total_goals = 0

    for cc in central_contents:
        year_str = cc.get("year", "")
        after_grade = parse_year_range(year_str)
        if after_grade is None:
            print(f"  Skipping unknown year range: {year_str}")
            continue

        label_local = f"Årskurs {year_str}"
        label_en = GRADE_BAND_LABELS_EN.get(year_str, f"Years {year_str}")

        sections = extract_central_content_sections(cc.get("text", ""))

        goals = []
        goal_index = 0
        for section in sections:
            for item in section["items"]:
                goal_index += 1
                goal_code = f"{designation or subject_code}-{year_str}-{goal_index}"
                verbs = extract_verbs(item)

                goal = {
                    "code": goal_code,
                    "text": {"local": item, "en": ""},
                    "coreElements": [section["heading"]] if section["heading"] else [],
                    "verbs": verbs,
                }
                goals.append(goal)
                total_goals += 1

        kr_for_band = [kr for kr in knowledge_reqs if str(kr.get("year", "")) == str(after_grade)]
        knowledge_criteria = []
        for kr in kr_for_band:
            grade_step = kr.get("gradeStep", "")
            kr_text = strip_html(kr.get("text", ""))
            if kr_text:
                knowledge_criteria.append({
                    "gradeStep": grade_step,
                    "text": {"local": kr_text, "en": ""},
                })

        band = {
            "afterGrade": after_grade,
            "label": {"local": label_local, "en": label_en},
            "competenceGoals": goals,
        }

        if knowledge_criteria:
            band["knowledgeCriteria"] = knowledge_criteria

        grade_bands.append(band)
        print(f"  Grade {after_grade}: {len(goals)} goals, {len(knowledge_criteria)} knowledge criteria")

    grade_bands.sort(key=lambda b: b["afterGrade"])

    subject_data = {
        "country": "sweden",
        "source": {
            "api": f"{BASE_URL}/subjects/{code}",
            "curriculum": "Lgr22",
            "license": "CC0",
            "lastSynced": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "subject": {
            "code": subject_code,
            "name": {"local": subject_name, "en": ENGLISH_NAMES.get(code, "")},
            "description": {"local": description_local, "en": ""},
            "coreElements": core_elements,
            "gradeBands": grade_bands,
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{filename}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(subject_data, f, ensure_ascii=False, indent=2)

    print(f"  Wrote {output_path.name} ({total_goals} goals across {len(grade_bands)} grade bands)")
    return subject_data


def update_metadata_timestamp():
    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        metadata["source"]["lastSynced"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg == "--list":
            print("Available Swedish grundskola subjects:\n")
            for code, filename in sorted(SUBJECTS.items()):
                en = ENGLISH_NAMES.get(code, "")
                print(f"  {code:16s} {filename:30s} {en}")
            return

        code = arg.upper()
        if code in SUBJECTS:
            sync_subject(code, SUBJECTS[code])
        else:
            print(f"Unknown subject code: {code}")
            print(f"Available: {', '.join(sorted(SUBJECTS.keys()))}")
            print("Use --list to see all subjects with names.")
            sys.exit(1)
    else:
        print(f"Syncing {len(SUBJECTS)} Swedish grundskola subjects from Skolverket API...\n")
        for code, filename in SUBJECTS.items():
            sync_subject(code, filename)

    update_metadata_timestamp()
    print("\nDone.")


if __name__ == "__main__":
    main()
