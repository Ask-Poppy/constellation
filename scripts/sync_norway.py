#!/usr/bin/env python3
"""
Sync Norwegian LK20 curriculum data from UDIR's public API.

Usage:
    python scripts/sync_norway.py              # Fetch all subjects
    python scripts/sync_norway.py MAT01-05     # Fetch single subject

API docs: https://github.com/Utdanningsdirektoratet/KL06-LK20-public/wiki/REST-(json)
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

BASE_URL = "https://data.udir.no/kl06/v201906"
OUTPUT_DIR = Path(__file__).parent.parent / "countries" / "norway" / "subjects"
METADATA_PATH = Path(__file__).parent.parent / "countries" / "norway" / "metadata.json"

SUBJECTS = {
    "MAT01-05": "mathematics",
    "NOR01-07": "norwegian",
    "ENG01-05": "english",
    "NAT01-04": "science",
    "SAF01-04": "social-studies",
    "RLE01-03": "religion-ethics",
    "KHV01-02": "arts-crafts",
    "MUS01-02": "music",
    "KRO01-05": "physical-education",
    "MHE01-02": "food-health",
    "FSP01-04": "foreign-language",
    "UTV01-03": "educational-choices",
    "ARB01-03": "work-life-studies",
}


def fetch_json(url: str, retries: int = 3) -> dict | None:
    for attempt in range(retries):
        try:
            time.sleep(0.15)
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read())
        except (URLError, json.JSONDecodeError) as e:
            if attempt < retries - 1:
                print(f"  Retry {attempt + 1}: {e}")
                time.sleep(1)
            else:
                print(f"  Failed: {url} — {e}")
                return None


def get_text(obj: dict | str, lang: str = "nob") -> str:
    if isinstance(obj, str):
        return obj
    if not isinstance(obj, dict):
        return ""
    if "tekst" in obj:
        for t in obj["tekst"]:
            if t.get("spraak") == lang:
                return t.get("verdi", "")
        for t in obj["tekst"]:
            if t.get("spraak") == "default":
                return t.get("verdi", "")
    if "verdi" in obj:
        return obj.get("verdi", "")
    return ""


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def extract_grade_number(title: str) -> int | None:
    match = re.search(r"(\d+)\.\s*trinn", title)
    if match:
        return int(match.group(1))
    return None


def extract_description(om_faget: dict) -> dict:
    frv = om_faget.get("fagets-relevans-og-verdier", {})
    relevans = frv.get("fagets-relevans", {})
    return {
        "local": clean_html(get_text(relevans.get("beskrivelse", {}), "nob")),
        "en": clean_html(get_text(relevans.get("beskrivelse", {}), "eng")),
    }


def extract_interdisciplinary_themes(om_faget: dict) -> list[dict]:
    ttf = om_faget.get("tverrfaglige-temaer-i-faget", {})
    themes = []
    for t in ttf.get("tverrfaglige-temaer", []):
        ref = t.get("referanse", {})
        themes.append({
            "code": ref.get("kode", ""),
            "name": {
                "local": clean_html(get_text(t.get("overskrift", {}), "nob")),
                "en": clean_html(get_text(t.get("overskrift", {}), "eng")),
            },
            "description": {
                "local": clean_html(get_text(t.get("beskrivelse", {}), "nob")),
                "en": clean_html(get_text(t.get("beskrivelse", {}), "eng")),
            },
        })
    return themes


def extract_basic_skills(om_faget: dict) -> list[dict]:
    gf = om_faget.get("grunnleggende-ferdigheter-i-faget", {})
    skills = []
    for s in gf.get("grunnleggende-ferdigheter", []):
        ref = s.get("referanse", {})
        skills.append({
            "code": ref.get("kode", "") if isinstance(ref, dict) else "",
            "name": {
                "local": clean_html(get_text(s.get("overskrift", {}), "nob")),
                "en": clean_html(get_text(s.get("overskrift", {}), "eng")),
            },
            "description": {
                "local": clean_html(get_text(s.get("beskrivelse", {}), "nob")),
                "en": clean_html(get_text(s.get("beskrivelse", {}), "eng")),
            },
        })
    return skills


def parse_assessment(vurderingsordninger: list[dict]) -> list[dict]:
    result = []
    for v in vurderingsordninger:
        title_nob = clean_html(get_text(v.get("overskrift", {}), "nob"))
        title_eng = clean_html(get_text(v.get("overskrift", {}), "eng"))
        desc_nob = clean_html(get_text(v.get("beskrivelse", {}), "nob"))
        result.append({
            "type": {
                "local": title_nob,
                "en": title_eng,
            },
            "description": {
                "local": desc_nob,
            },
        })
    return result


def match_assessment_to_grade(assessment_entries: list[dict], after_grade: int) -> list[dict]:
    grade_labels = {
        2: "2. trinn", 4: "4. trinn", 7: "7. trinn", 10: "10. trinn",
        11: "vg1", 12: "vg2", 13: "vg3",
    }
    label = grade_labels.get(after_grade, f"{after_grade}. trinn")
    matched = []
    for entry in assessment_entries:
        desc = entry["description"]["local"].lower()
        if label.lower() in desc:
            matched.append(entry)
    return matched


def sync_subject(code: str, filename: str) -> dict | None:
    print(f"\nFetching {code}...")

    curriculum = fetch_json(f"{BASE_URL}/laereplaner-lk20/{code}")
    if not curriculum:
        return None

    subject_name_local = get_text(curriculum.get("tittel", {}), "nob")
    subject_name_en = get_text(curriculum.get("tittel", {}), "eng")

    om_faget = curriculum.get("om-faget-kapittel", {})

    description = extract_description(om_faget)
    interdisciplinary_themes = extract_interdisciplinary_themes(om_faget)
    basic_skills = extract_basic_skills(om_faget)

    vk = curriculum.get("vurderingsordninger-kapittel", {})
    all_assessment = parse_assessment(vk.get("vurderingsordninger", []))

    core_elements = []
    ke_section = om_faget.get("kjerneelementer-i-faget", {})
    for ke_ref in ke_section.get("kjerneelementer", []):
        ke_code = ke_ref.get("kode")
        if ke_code:
            ke = fetch_json(f"{BASE_URL}/kjerneelementer-lk20/{ke_code}")
            if ke:
                core_elements.append({
                    "code": ke_code,
                    "name": {
                        "local": clean_html(get_text(ke.get("tittel", {}), "nob")),
                        "en": clean_html(get_text(ke.get("tittel", {}), "eng")),
                    },
                    "description": {
                        "local": clean_html(get_text(ke.get("beskrivelse", {}), "nob")),
                        "en": clean_html(get_text(ke.get("beskrivelse", {}), "eng")),
                    },
                })

    km_chapter = curriculum.get("kompetansemaal-kapittel", {})
    km_sets = km_chapter.get("kompetansemaalsett", [])

    grade_bands = []
    total_goals = 0

    for km_set_ref in km_sets:
        km_set_code = km_set_ref.get("kode")
        if not km_set_code:
            continue

        km_set = fetch_json(f"{BASE_URL}/kompetansemaalsett-lk20/{km_set_code}")
        if not km_set:
            continue

        label_local = get_text(km_set.get("tittel", {}), "nob")
        label_en = get_text(km_set.get("tittel", {}), "eng")

        after_grade = extract_grade_number(label_local)
        if after_grade is None:
            if "vg1" in label_local.lower():
                after_grade = 11
            elif "vg2" in label_local.lower():
                after_grade = 12
            elif "vg3" in label_local.lower():
                after_grade = 13
            else:
                max_grade = 0
                for trinn in km_set.get("etter-aarstrinn", []):
                    trinn_code = trinn.get("kode", "")
                    m = re.search(r"aarstrinn(\d+)", trinn_code)
                    if m:
                        max_grade = max(max_grade, int(m.group(1)))
                    elif trinn_code == "vg1":
                        max_grade = max(max_grade, 11)
                    elif trinn_code == "vg2":
                        max_grade = max(max_grade, 12)
                    elif trinn_code == "vg3":
                        max_grade = max(max_grade, 13)
                if max_grade > 0:
                    after_grade = max_grade
                else:
                    continue

        goals = []
        for km_ref in km_set.get("kompetansemaal", []):
            km_code = km_ref.get("kode")
            if not km_code:
                continue

            km = fetch_json(f"{BASE_URL}/kompetansemaal-lk20/{km_code}")
            if not km:
                continue

            goal_core_elements = []
            for ke in km.get("tilknyttede-kjerneelementer", []):
                ref = ke.get("referanse", {})
                name = ref.get("tittel")
                if name:
                    goal_core_elements.append(clean_html(name))

            goal_verbs = []
            for v in km.get("tilknyttede-verb", []):
                name = v.get("tittel")
                if name:
                    goal_verbs.append(clean_html(name))

            goals.append({
                "code": km_code,
                "text": {
                    "local": clean_html(get_text(km.get("tittel", {}), "nob")),
                    "en": clean_html(get_text(km.get("tittel", {}), "eng")),
                },
                "coreElements": goal_core_elements,
                "verbs": goal_verbs,
            })

            total_goals += 1

        band = {
            "afterGrade": after_grade,
            "label": {"local": label_local, "en": label_en},
            "competenceGoals": goals,
        }

        grade_assessment = match_assessment_to_grade(all_assessment, after_grade)
        if grade_assessment:
            band["assessment"] = grade_assessment

        grade_bands.append(band)

        print(f"  Grade {after_grade}: {len(goals)} goals")

    grade_bands.sort(key=lambda b: b["afterGrade"])

    subject_data = {
        "country": "norway",
        "source": {
            "api": f"{BASE_URL}/laereplaner-lk20/{code}",
            "curriculum": "LK20",
            "license": "NLOD",
            "lastSynced": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "subject": {
            "code": code,
            "name": {"local": subject_name_local, "en": subject_name_en},
            "description": description,
            "coreElements": core_elements,
            "interdisciplinaryThemes": interdisciplinary_themes,
            "basicSkills": basic_skills,
            "gradeBands": grade_bands,
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{filename}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(subject_data, f, ensure_ascii=False, indent=2)

    print(f"  Wrote {output_path.name} ({total_goals} goals)")
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
        code = sys.argv[1].upper()
        if code in SUBJECTS:
            sync_subject(code, SUBJECTS[code])
        else:
            print(f"Unknown subject code: {code}")
            print(f"Available: {', '.join(SUBJECTS.keys())}")
            sys.exit(1)
    else:
        print(f"Syncing {len(SUBJECTS)} Norwegian subjects from UDIR API...\n")
        for code, filename in SUBJECTS.items():
            sync_subject(code, filename)

    update_metadata_timestamp()
    print("\nDone.")


if __name__ == "__main__":
    main()
