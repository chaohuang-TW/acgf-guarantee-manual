#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

def run_validation():
    with open(DATA_DIR / "related-forms.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(DATA_DIR / "version.json", "r", encoding="utf-8") as f:
        version = json.load(f)["id"]

    with open(DATA_DIR / "reading-units.json", "r", encoding="utf-8") as f:
        units_data = json.load(f)
        unit_ids = {u["id"] for u in units_data["units"]}

    with open(DATA_DIR / "toc.json", "r", encoding="utf-8") as f:
        toc = json.load(f)
        form_numbers = {f["code"].replace("格式 ", "") for f in toc["forms"] + toc["specialForms"]}

    if data["version"] != version:
        raise ValueError(f"Version mismatch: {data['version']} != {version}")

    relations = data["relations"]
    seen_relations = set()

    for r in relations:
        if r["contentRef"]["id"] not in unit_ids:
            raise ValueError(f"Unknown reading unit ID: {r['contentRef']['id']}")

        if r["form"]["number"] not in form_numbers:
            raise ValueError(f"Unknown form number: {r['form']['number']}")

        key = (r["contentRef"]["id"], r["form"]["number"])
        if key in seen_relations:
            raise ValueError(f"Duplicate relation detected: {key}")
        seen_relations.add(key)

        if not r.get("evidence"):
            raise ValueError(f"No evidence for relation: {key}")

    print("Related Forms validation passed.")

if __name__ == "__main__":
    run_validation()
