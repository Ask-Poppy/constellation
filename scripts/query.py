#!/usr/bin/env python3
"""
Query curriculum data locally or from GitHub.

Usage:
    python scripts/query.py norway 5 mathematics     # Goals for grade 5 math
    python scripts/query.py norway 7                  # All goals for grade 7
    python scripts/query.py norway --list             # List available subjects
    python scripts/query.py --stats                   # Overview of all data
"""

import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "countries"


def load_subject(country: str, subject: str) -> dict | None:
    path = DATA_DIR / country / "subjects" / f"{subject}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_subjects(country: str):
    subject_dir = DATA_DIR / country / "subjects"
    if not subject_dir.exists():
        print(f"No data for country: {country}")
        return

    print(f"\n{country.upper()} subjects:\n")
    for path in sorted(subject_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        name = data["subject"]["name"]
        code = data["subject"]["code"]
        bands = len(data["subject"]["gradeBands"])
        goals = sum(len(b["competenceGoals"]) for b in data["subject"]["gradeBands"])
        print(f"  {path.stem:25s} {code:12s} {name['en'] or name['local']:30s} {bands} bands, {goals} goals")


def get_goals(country: str, grade: int, subject: str | None = None):
    subject_dir = DATA_DIR / country / "subjects"
    if not subject_dir.exists():
        print(f"No data for country: {country}")
        return

    files = [subject_dir / f"{subject}.json"] if subject else sorted(subject_dir.glob("*.json"))

    for path in files:
        if not path.exists():
            print(f"Subject not found: {path.stem}")
            continue

        data = json.loads(path.read_text(encoding="utf-8"))
        subj = data["subject"]
        name = subj["name"]["en"] or subj["name"]["local"]

        for band in subj["gradeBands"]:
            after_grade = band["afterGrade"]
            prev_checkpoint = 0
            for b in subj["gradeBands"]:
                if b["afterGrade"] < after_grade and b["afterGrade"] > prev_checkpoint:
                    prev_checkpoint = b["afterGrade"]

            if prev_checkpoint < grade <= after_grade:
                print(f"\n{'=' * 60}")
                print(f"{name} — {band['label'].get('en') or band['label']['local']}")
                print(f"{'=' * 60}")
                for i, goal in enumerate(band["competenceGoals"], 1):
                    text = goal["text"].get("en") or goal["text"]["local"]
                    print(f"\n  {i}. {text}")
                    if goal.get("coreElements"):
                        print(f"     Core: {', '.join(goal['coreElements'])}")
                break


def stats():
    print("\nConstellation — Curriculum Data Overview\n")

    for country_dir in sorted(DATA_DIR.iterdir()):
        if not country_dir.is_dir():
            continue

        metadata_path = country_dir / "metadata.json"
        if metadata_path.exists():
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            country_name = meta["country"]["name"]["en"]
            curriculum = meta["system"]["curriculum"]
            synced = meta["source"].get("lastSynced", "never")
        else:
            country_name = country_dir.name
            curriculum = "?"
            synced = "never"

        subject_dir = country_dir / "subjects"
        if not subject_dir.exists():
            continue

        total_goals = 0
        total_subjects = 0
        for path in subject_dir.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            total_subjects += 1
            for band in data["subject"]["gradeBands"]:
                total_goals += len(band["competenceGoals"])

        print(f"  {country_name} ({curriculum})")
        print(f"    {total_subjects} subjects, {total_goals} goals")
        print(f"    Last synced: {synced}")
        print()


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/query.py --stats                    Overview")
        print("  python scripts/query.py norway --list              List subjects")
        print("  python scripts/query.py norway 5 mathematics       Goals for grade 5 math")
        print("  python scripts/query.py norway 7                   All goals for grade 7")
        return

    if sys.argv[1] == "--stats":
        stats()
        return

    country = sys.argv[1].lower()

    if len(sys.argv) > 2 and sys.argv[2] == "--list":
        list_subjects(country)
        return

    if len(sys.argv) > 2:
        grade = int(sys.argv[2])
        subject = sys.argv[3] if len(sys.argv) > 3 else None
        get_goals(country, grade, subject)
    else:
        list_subjects(country)


if __name__ == "__main__":
    main()
