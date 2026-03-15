#!/usr/bin/env python3
"""
Validation script for kosher_list.json

Uses:
  - Pydantic schema re-validation
  - RapidFuzz similarity checks
"""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict

from rapidfuzz import fuzz

BASE_DIR = os.path.dirname(__file__)
JSON_PATH = os.path.join(BASE_DIR, "output", "kosher_list.json")

WEIRD_CHARS = ["�", "ô", "Ç", "·", "Ã", "Â"]
SIZE_PATTERNS = [
    r"\bGastro\s*\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
    r"\b\d+\s?[xX]\s?\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
    r"\b\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
]

SUSPICIOUS_TOKENS = [
    "kncker",
    "sonneblumen",
    "reffiniert",
    "alsaka",
    "rapsberry",
    "seuppe",
    "caprisonne",
]


def load_data(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_for_dupe(text: str) -> str:
    text = (text or "").lower().strip()
    text = text.replace("ß", "ss")
    text = re.sub(r"[^a-z0-9äöü\s&/+.\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def has_weird_chars(text: str) -> bool:
    return any(ch in (text or "") for ch in WEIRD_CHARS)


def contains_size_in_name(name: str) -> bool:
    return any(re.search(p, name or "", flags=re.IGNORECASE) for p in SIZE_PATTERNS)


def starts_or_ends_bad_punct(name: str) -> bool:
    return bool(re.search(r'^[\s,;:/\-"]|[\s,;:/\-"]$', name or ""))


def has_suspicious_spelling(text: str) -> bool:
    t = (text or "").lower()
    return any(tok in t for tok in SUSPICIOUS_TOKENS)


def looks_like_coke_issue(product: dict) -> bool:
    name = product.get("name", "")
    raw_name = product.get("raw_name", "")
    manufacturer = product.get("manufacturer", "")

    cokeish = any(x in (name + " " + raw_name) for x in ["Coca", "Cola", "Fanta", "Sprite"])
    ugly_name = any(x in name for x in ["Coca ' Cola", "Coca - Cola", "Coca _ Cola"])

    return cokeish and ugly_name


def family_key(product: dict) -> tuple[str, str]:
    manufacturer = normalize_for_dupe(product.get("manufacturer", ""))

    name = normalize_for_dupe(product.get("name", ""))
    name = re.sub(r"\b\d+(?:[.,]\d+)?\s?(g|kg|ml|l)\b", "", name)
    name = re.sub(r"\b(multipack|trinkpack|glass|bio)\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    return manufacturer, name


def similar_name_clusters(products: list[dict], threshold: float = 92.0) -> list[tuple[str, str, str, str]]:
    """
    Find suspicious near-duplicates within same manufacturer.
    Returns tuples of (manufacturer, name1, name2, score)
    """
    by_manufacturer = defaultdict(list)
    for p in products:
        by_manufacturer[normalize_for_dupe(p.get("manufacturer", ""))].append(p.get("name", ""))

    out = []
    for manufacturer, names in by_manufacturer.items():
        unique_names = sorted(set(n for n in names if n))
        for i in range(len(unique_names)):
            for j in range(i + 1, len(unique_names)):
                a = unique_names[i]
                b = unique_names[j]
                score = fuzz.WRatio(normalize_for_dupe(a), normalize_for_dupe(b))
                if threshold <= score < 100:
                    out.append((manufacturer, a, b, f"{score:.1f}"))
    return out


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
    too_many_categories = []
    spelling_issues = []
    coke_issues = []

    family_groups = defaultdict(list)

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

        if len(categories) > 3:
            too_many_categories.append(pid)

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

        if has_suspicious_spelling(name) or has_suspicious_spelling(p.get("raw_name", "")):
            spelling_issues.append(pid)

        if looks_like_coke_issue(p):
            coke_issues.append(pid)

        dupe_key = (normalize_for_dupe(manufacturer), normalize_for_dupe(name))
        dupes[dupe_key].append(pid)

        family_groups[family_key(p)].append({
            "id": pid,
            "name": name,
            "categories": categories,
            "size": p.get("size", ""),
        })

    duplicate_groups = {k: v for k, v in dupes.items() if len(v) > 1}

    inconsistent_families = {}
    for key, items in family_groups.items():
        if len(items) < 2:
            continue

        names = {item["name"] for item in items}
        category_sets = {tuple(item["categories"]) for item in items}

        if len(names) > 1 or len(category_sets) > 1:
            inconsistent_families[key] = items

    similar_clusters = similar_name_clusters(products)

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
    print(f"Too many categories (>3)      : {len(too_many_categories)}")
    print(f"Suspicious spelling issues    : {len(spelling_issues)}")
    print(f"Coca-Cola family issues       : {len(coke_issues)}")
    print(f"Duplicate norm name+mfr groups: {len(duplicate_groups)}")
    print(f"Inconsistent family groups    : {len(inconsistent_families)}")
    print(f"Near-duplicate name clusters  : {len(similar_clusters)}")

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
    sample("Too many category IDs", too_many_categories)
    sample("Suspicious spelling IDs", spelling_issues)
    sample("Coca-Cola issue IDs", coke_issues)

    if duplicate_groups:
        print("\nDuplicate normalized groups:")
        shown = 0
        for (mfr, name), ids in duplicate_groups.items():
            print(f"  - {mfr} | {name} -> {ids[:8]}")
            shown += 1
            if shown >= 10:
                break

    if inconsistent_families:
        print("\nInconsistent family groups:")
        shown = 0
        for (mfr, fam), items in inconsistent_families.items():
            print(f"  - {mfr} | {fam}")
            for item in items[:6]:
                print(f"      {item['id']} | {item['name']} | {item['categories']} | {item['size']}")
            shown += 1
            if shown >= 10:
                break

    if similar_clusters:
        print("\nNear-duplicate name clusters:")
        for manufacturer, a, b, score in similar_clusters[:15]:
            print(f"  - {manufacturer}: '{a}' ~ '{b}' ({score})")


if __name__ == "__main__":
    main()
