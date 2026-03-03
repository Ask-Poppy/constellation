#!/usr/bin/env python3
"""
Sync Finnish POPS 2014 curriculum data from the ePerusteet API.

Usage:
    python scripts/sync_finland.py              # Fetch all subjects
    python scripts/sync_finland.py MA           # Fetch single subject by code

API docs: https://opetushallitus.github.io/eperusteet/api/eperusteet
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

BASE_URL = "https://eperusteet.opintopolku.fi/eperusteet-service/api/external"
PERUSTE_ID = 419550
OUTPUT_DIR = Path(__file__).parent.parent / "countries" / "finland" / "subjects"
METADATA_PATH = Path(__file__).parent.parent / "countries" / "finland" / "metadata.json"

VLK_MAP = {
    428780: {"afterGrade": 2, "local": "Vuosiluokat 1–2", "en": "Grades 1–2"},
    428781: {"afterGrade": 6, "local": "Vuosiluokat 3–6", "en": "Grades 3–6"},
    428782: {"afterGrade": 9, "local": "Vuosiluokat 7–9", "en": "Grades 7–9"},
}

SUBJECT_FILENAMES = {
    "AI": "mother-tongue",
    "MA": "mathematics",
    "YL": "environmental-studies",
    "BI": "biology",
    "GE": "geography",
    "FY": "physics",
    "KE": "chemistry",
    "TE": "health-education",
    "HI": "history",
    "YH": "social-studies",
    "MU": "music",
    "KU": "visual-arts",
    "KS": "crafts",
    "LI": "physical-education",
    "KO": "home-economics",
    "OP": "guidance-counselling",
    "KT": "religion",
    "VK": "foreign-languages",
    "TK": "second-national-language",
}

SUBJECT_NAMES_EN = {
    "AI": "Mother Tongue and Literature",
    "MA": "Mathematics",
    "YL": "Environmental Studies",
    "BI": "Biology",
    "GE": "Geography",
    "FY": "Physics",
    "KE": "Chemistry",
    "TE": "Health Education",
    "HI": "History",
    "YH": "Social Studies",
    "MU": "Music",
    "KU": "Visual Arts",
    "KS": "Crafts",
    "LI": "Physical Education",
    "KO": "Home Economics",
    "OP": "Guidance Counselling",
    "KT": "Religion",
    "VK": "Foreign Languages (English)",
    "TK": "Second National Language",
}

COMPOSITE_PRIMARY = {
    "AI": "AI1",
    "KT": "KT1",
    "VK": "A1",
    "TK": "RUA",
}

COMPOSITE_PRIMARY_NAME_HINT = {
    "VK": "Englanti",
    "TK": "Ruotsin kieli, A-oppimäärä",
}


def fetch_json(url: str, retries: int = 3) -> dict | list | None:
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


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def get_fi(obj: dict | None) -> str:
    if not obj or not isinstance(obj, dict):
        return ""
    return obj.get("fi", "")


def get_sv(obj: dict | None) -> str:
    if not obj or not isinstance(obj, dict):
        return ""
    return obj.get("sv", "")


def extract_tavoite_code(text: str) -> str:
    match = re.match(r"^(T\d+)\b", text.strip())
    if match:
        return match.group(1)
    return ""


def max_grade_from_vuosiluokat(vuosiluokat: list[str]) -> int | None:
    grades = []
    for v in vuosiluokat:
        match = re.search(r"(\d+)", v)
        if match:
            grades.append(int(match.group(1)))
    return max(grades) if grades else None


def build_content_area_map(sisaltoalueet: list[dict]) -> dict[int, dict]:
    result = {}
    for sa in sisaltoalueet:
        sa_id = sa.get("id")
        nimi = sa.get("nimi", {})
        nimi_fi = get_fi(nimi)
        code_match = re.match(r"^(S\d+)\b", nimi_fi)
        code = code_match.group(1) if code_match else ""
        result[sa_id] = {
            "code": code,
            "name": clean_html(nimi_fi),
        }
    return result


def build_kohdealue_map(kohdealueet: list[dict]) -> dict[int, str]:
    result = {}
    for ka in kohdealueet:
        ka_id = ka.get("id")
        nimi_fi = get_fi(ka.get("nimi", {}))
        result[ka_id] = clean_html(nimi_fi)
    return result


def process_vuosiluokkakokonaisuudet(
    vlk_list: list[dict],
    kohdealue_map: dict[int, str],
    existing_bands: list[dict] | None = None,
) -> list[dict]:
    existing_bands_map = {}
    for eb in (existing_bands or []):
        existing_bands_map[eb.get("afterGrade")] = eb

    grade_bands = []

    for vlk in vlk_list:
        vlk_ref = vlk.get("_vuosiluokkaKokonaisuus")
        vlk_info = VLK_MAP.get(vlk_ref)

        if not vlk_info:
            vuosiluokat = vlk.get("vuosiluokat", [])
            after_grade = max_grade_from_vuosiluokat(vuosiluokat)
            if after_grade is None:
                continue
            grade_nums = []
            for v in vuosiluokat:
                m = re.search(r"(\d+)", v)
                if m:
                    grade_nums.append(int(m.group(1)))
            min_grade = min(grade_nums) if grade_nums else after_grade
            vlk_info = {
                "afterGrade": after_grade,
                "local": f"Vuosiluokat {min_grade}\u2013{after_grade}",
                "en": f"Grades {min_grade}\u2013{after_grade}",
            }

        sa_map = build_content_area_map(vlk.get("sisaltoalueet", []))

        existing_band = existing_bands_map.get(vlk_info["afterGrade"], {})
        existing_goals_map = {}
        for eg in existing_band.get("competenceGoals", []):
            existing_goals_map[eg.get("code", "")] = eg

        goals = []
        for t in vlk.get("tavoitteet", []):
            tavoite = t.get("tavoite", {})
            tavoite_fi = get_fi(tavoite)
            tavoite_sv = get_sv(tavoite)

            code = extract_tavoite_code(tavoite_fi)

            linked_content_areas = []
            for sa_ref in t.get("sisaltoalueet", []):
                sa_id = int(sa_ref) if isinstance(sa_ref, str) else sa_ref
                if sa_id in sa_map:
                    area = sa_map[sa_id]
                    label = area["code"] if area["code"] else area["name"]
                    if label:
                        linked_content_areas.append(label)

            linked_kohdealueet = []
            for ka_ref in t.get("kohdealueet", []):
                ka_id = int(ka_ref) if isinstance(ka_ref, str) else ka_ref
                if ka_id in kohdealue_map:
                    linked_kohdealueet.append(kohdealue_map[ka_id])

            existing_goal = existing_goals_map.get(code, {})
            goals.append({
                "code": code,
                "text": {
                    "local": clean_html(tavoite_fi),
                    "en": existing_goal.get("text", {}).get("en", ""),
                },
                "coreElements": linked_content_areas,
                "verbs": [],
            })

        grade_bands.append({
            "afterGrade": vlk_info["afterGrade"],
            "label": {
                "local": vlk_info["local"],
                "en": vlk_info["en"],
            },
            "competenceGoals": goals,
        })

        print(f"  Grade {vlk_info['afterGrade']}: {len(goals)} goals")

    grade_bands.sort(key=lambda b: b["afterGrade"])
    return grade_bands


def find_primary_oppimaaara(subject_data: dict, code: str) -> dict | None:
    target_code = COMPOSITE_PRIMARY.get(code)
    if not target_code:
        return None
    name_hint = COMPOSITE_PRIMARY_NAME_HINT.get(code, "")
    candidates = [
        om for om in subject_data.get("oppimaarat", [])
        if om.get("koodiArvo") == target_code
    ]
    if name_hint and len(candidates) > 1:
        for c in candidates:
            if name_hint in get_fi(c.get("nimi", {})):
                return c
    if candidates:
        return candidates[0]
    oppimaarat = subject_data.get("oppimaarat", [])
    return oppimaarat[0] if oppimaarat else None


def load_existing(filepath: Path) -> dict | None:
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def sync_subject(subject_meta: dict) -> dict | None:
    subject_id = subject_meta["id"]
    code = subject_meta["koodiArvo"]
    name_fi = get_fi(subject_meta.get("nimi", {}))
    is_composite = subject_meta.get("koosteinen", False)

    filename = SUBJECT_FILENAMES.get(code)
    if not filename:
        print(f"  Skipping {code} ({name_fi}) — no filename mapping")
        return None

    name_en = SUBJECT_NAMES_EN.get(code, "")

    output_path = OUTPUT_DIR / f"{filename}.json"
    existing = load_existing(output_path)
    existing_subject = existing.get("subject", {}) if existing else {}

    print(f"\nFetching {code} — {name_fi}...")

    detail = fetch_json(f"{BASE_URL}/peruste/{PERUSTE_ID}/perusopetus/oppiaineet/{subject_id}")
    if not detail:
        return None

    tehtava = detail.get("tehtava", {})
    tehtava_teksti = tehtava.get("teksti", {}) if isinstance(tehtava, dict) else {}
    description_fi = clean_html(get_fi(tehtava_teksti)) if isinstance(tehtava_teksti, dict) else ""

    kohdealue_map = build_kohdealue_map(detail.get("kohdealueet", []))

    source_data = detail
    source_code = code
    source_name_fi = name_fi

    if is_composite:
        primary = find_primary_oppimaaara(detail, code)
        if primary:
            source_data = primary
            source_code = primary.get("koodiArvo", code)
            primary_name = get_fi(primary.get("nimi", {}))
            if primary_name:
                source_name_fi = primary_name
            print(f"  Using primary sub-subject: {source_code} — {source_name_fi}")
            kohdealue_map.update(build_kohdealue_map(primary.get("kohdealueet", [])))
        else:
            print(f"  Warning: composite subject {code} has no sub-subjects with data")

    vlk_list = source_data.get("vuosiluokkakokonaisuudet", [])
    if not vlk_list:
        print(f"  No grade bands found for {code}")
        return None

    existing_core_map = {}
    for ce in existing_subject.get("coreElements", []):
        local_key = ce.get("name", {}).get("local", "")
        if local_key:
            existing_core_map[local_key] = ce

    content_areas = []
    seen_areas = set()
    for vlk in vlk_list:
        for sa in vlk.get("sisaltoalueet", []):
            nimi_fi = get_fi(sa.get("nimi", {}))
            if nimi_fi and nimi_fi not in seen_areas:
                seen_areas.add(nimi_fi)
                clean_name = clean_html(nimi_fi)
                existing_ce = existing_core_map.get(clean_name, {})
                content_areas.append({
                    "code": re.match(r"^(S\d+)\b", nimi_fi).group(1) if re.match(r"^(S\d+)\b", nimi_fi) else "",
                    "name": {"local": clean_name, "en": existing_ce.get("name", {}).get("en", "")},
                    "description": {"local": clean_html(get_fi(sa.get("kuvaus", {}))), "en": existing_ce.get("description", {}).get("en", "")},
                })

    grade_bands = process_vuosiluokkakokonaisuudet(
        vlk_list, kohdealue_map, existing_subject.get("gradeBands")
    )
    total_goals = sum(len(gb["competenceGoals"]) for gb in grade_bands)

    existing_desc_en = existing_subject.get("description", {}).get("en", "")

    source_block = {
        "api": f"{BASE_URL}/peruste/{PERUSTE_ID}/perusopetus/oppiaineet/{subject_id}",
        "curriculum": "POPS 2014",
        "license": "Open Government Data (Finland)",
        "lastSynced": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    existing_source = existing.get("source", {}) if existing else {}
    if "aiEnriched" in existing_source:
        source_block["aiEnriched"] = existing_source["aiEnriched"]

    new_subject = {
        "code": code,
        "name": {"local": source_name_fi, "en": name_en},
        "description": {"local": description_fi, "en": existing_desc_en},
        "coreElements": content_areas,
    }

    for extra_key in ("interdisciplinaryThemes", "basicSkills"):
        if extra_key in existing_subject:
            new_subject[extra_key] = existing_subject[extra_key]

    new_subject["gradeBands"] = grade_bands

    subject_data = {
        "country": "finland",
        "source": source_block,
        "subject": new_subject,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(subject_data, f, ensure_ascii=False, indent=2)

    print(f"  Wrote {output_path.name} ({total_goals} goals, {len(content_areas)} content areas)")
    return subject_data


def update_metadata_timestamp():
    if METADATA_PATH.exists():
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        metadata["source"]["lastSynced"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with open(METADATA_PATH, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)


def main():
    print(f"Fetching subject list from ePerusteet (peruste {PERUSTE_ID})...\n")

    subjects = fetch_json(f"{BASE_URL}/peruste/{PERUSTE_ID}/perusopetus/oppiaineet")
    if not subjects:
        print("Failed to fetch subject list")
        sys.exit(1)

    print(f"Found {len(subjects)} subjects\n")

    target_code = None
    if len(sys.argv) > 1:
        target_code = sys.argv[1].upper()

    seen_codes = set()
    synced = 0
    skipped_duplicates = []

    for subject in subjects:
        code = subject.get("koodiArvo", "")
        name_fi = get_fi(subject.get("nimi", {}))

        if target_code and code != target_code:
            continue

        if code in seen_codes:
            skipped_duplicates.append(f"{code} ({name_fi})")
            continue
        seen_codes.add(code)

        if code == "KT" and subject.get("koosteinen"):
            result = sync_subject(subject)
        elif code == "KT" and not subject.get("koosteinen"):
            continue
        else:
            result = sync_subject(subject)

        if result:
            synced += 1

    if skipped_duplicates:
        print(f"\nSkipped duplicate codes: {', '.join(skipped_duplicates)}")

    update_metadata_timestamp()
    print(f"\nDone. Synced {synced} subjects.")


if __name__ == "__main__":
    main()
