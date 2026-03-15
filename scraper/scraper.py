#!/usr/bin/env python3
"""
Validation script for kosher_list.json

Checks:
- weird characters
- legacy fields
- empty manufacturers/categories
- duplicate normalized products per manufacturer
- suspicious generic entries
- names still containing size patterns
- punctuation anomalies
"""

import json
import os
import re
from collections import defaultdict

BASE_DIR = os.path.dirname(__file__)
JSON_PATH = os.path.join(BASE_DIR, "output", "kosher_list.json")

WEIRD_CHARS = ["�", "ô", "Ç", "·", "Ã", "Â"]
SIZE_PATTERNS = [
    r"\bGastro\s*\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
    r"\b\d+\s?[xX]\s?\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
    r"\b\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
]


def load_data(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_for_dupe(text: str) -> str:
    text = (text or "").lower().strip()
    text = text.replace("ß", "ss")
    text = re.sub(r"[^a-z0-9äöü\s&/+.-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def has_weird_chars(text: str) -> bool:
    return any(ch in (text or "") for ch in WEIRD_CHARS)


def contains_size_in_name(name: str) -> bool:
    return any(re.search(p, name or "", flags=re.IGNORECASE) for p in SIZE_PATTERNS)


def starts_or_ends_bad_punct(name: str) -> bool:
    return bool(re.search(r'^[\s,;:/\-"]|[\s,;:/\-"]$', name or ""))


def main():
    data = load_data(JSON_PATH)
    products = data.get("products", [])

    weird = []
    legacy = []
    empty_manufacturer = []
    empty_categories = []
    dupes = defaultdict(list)
    generic_scope_mismatch = []
    size_leaks = []
    bad_punct = []
    empty_match_name = []

    for p in products:
        pid = p.get("id", "")
        name = p.get("name", "")
        manufacturer = p.get("manufacturer", "")
        scope = p.get("scope", "")
        categories = p.get("categories", [])

        if "weitere_kategorien" in p:
            legacy.append(pid)

        if not manufacturer:
            empty_manufacturer.append(pid)

        if not categories:
            empty_categories.append(pid)

        if manufacturer.lower() == "alle firmen" and scope != "generic_rule":
            generic_scope_mismatch.append(pid)

        if has_weird_chars(name) or has_weird_chars(p.get("raw_name", "")) or has_weird_chars(manufacturer):
            weird.append(pid)

        if contains_size_in_name(name):
            size_leaks.append(pid)

        if starts_or_ends_bad_punct(name):
            bad_punct.append(pid)

        if not p.get("match_name"):
            empty_match_name.append(pid)

        dupe_key = (normalize_for_dupe(manufacturer), normalize_for_dupe(name))
        dupes[dupe_key].append(pid)

    duplicate_groups = {k: v for k, v in dupes.items() if len(v) > 1}

    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    print(f"Products total                : {len(products)}")
    print(f"Legacy field present          : {len(legacy)}")
    print(f"Weird characters              : {len(weird)}")
    print(f"Empty manufacturer            : {len(empty_manufacturer)}")
    print(f"Empty categories              : {len(empty_categories)}")
    print(f"Generic scope mismatch        : {len(generic_scope_mismatch)}")
    print(f"Names still containing size   : {len(size_leaks)}")
    print(f"Bad punctuation edges         : {len(bad_punct)}")
    print(f"Missing match_name            : {len(empty_match_name)}")
    print(f"Duplicate norm name+mfr groups: {len(duplicate_groups)}")

    def sample(title: str, ids: list[str], n: int = 10):
        if not ids:
            return
        print(f"\n{title}:")
        for pid in ids[:n]:
            print(f"  - {pid}")

    sample("Legacy field IDs", legacy)
    sample("Weird char IDs", weird)
    sample("Empty manufacturer IDs", empty_manufacturer)
    sample("Empty categories IDs", empty_categories)
    sample("Generic scope mismatch IDs", generic_scope_mismatch)
    sample("Size leak IDs", size_leaks)
    sample("Bad punctuation IDs", bad_punct)
    sample("Missing match_name IDs", empty_match_name)

    if duplicate_groups:
        print("\nDuplicate normalized groups:")
        shown = 0
        for (mfr, name), ids in duplicate_groups.items():
            print(f"  - {mfr} | {name} -> {ids[:8]}")
            shown += 1
            if shown >= 10:
                break


if __name__ == "__main__":
    main()
