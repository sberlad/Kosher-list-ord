#!/usr/bin/env python3
"""
ORD Koscherliste Scraper

Outputs:
  - output/kosher_list.json
  - output/manifest.json

Focus:
  - stronger data quality
  - canonical schema enforcement
  - generic-rule detection
  - better category normalization
  - safer casing and text repair
"""

import hashlib
import html
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://koscherliste.ordonline.de/koscherliste/"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; KosherListBot/1.0; "
        "+https://github.com/sberlad/Kosher-list-ord)"
    )
}

CERT_SUFFIXES = [
    "Rabbiner Tuvia Hod Hochwald",
    "Rabbiner Jona Pawel",
    "Rabbiner Meir Hord",
    "Rabbiner  Meir Hord",
    "Rabbiner Jaron Engelmayer",
    "Rabbiner Avichai Apel",
    "Rabbiner Mark (Mordechai) Pavlovsky",
    "Rabbiner Mark Pavlovsky",
    "Rabbiner Moshe Flomenmann",
    "Rabbiner Zsolt Balla",
    "Rabbiner Dov Levy Barsilay",
    "Rabbiner Hazan",
    "Rabbiner Garelik",
    "Rabbiner P. Padwa",
    "Rabbiner Padwa",
    "Rabbiner Israel Meir Levinger",
    "Orthodox Union",
    "London Beit Din",
    "Manchester Kosher",
    "Manchester Beit Din",
    "Basel Kosher Commission",
    "K Meschulasch Oberrabbiner Liebermann",
    "Kof-K",
    "KLBD",
]

BRAND_SUFFIXES = [
    "Balisto",
    "Bounty",
    "BRôLIO",
    "Vivani",
]

LEGAL_SUFFIXES = [
    "GmbH",
    "mbH",
    "AG",
    "KG",
    "e.K.",
    "e. K.",
    "e.Kfm.",
    "e.Kfr.",
    "OHG",
    "UG",
    "SE",
    "Ltd.",
    "Limited",
    "LLC",
    "Inc.",
    "Corp.",
    "Co.",
    "S.A.",
    "S.R.L.",
    "S.p.A.",
]

SIZE_PATTERNS = [
    r"\bGastro\s*\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
    r"\b\d+\s?[xX]\s?\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
    r"\b\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l)\b",
]

HEADER_LIKE_NAMES = {
    "artikelbezeichnung",
    "produkt",
    "produktbezeichnung",
    "bezeichnung",
}

ACRONYMS = {
    "ABC", "B&J", "BJ", "FT", "GFY", "IC", "EU", "UK", "LLC", "KG",
    "D.O.P.", "DOP", "USA", "UHT", "BBQ", "XL", "XXL"
}

CATEGORY_ALIAS_MAP = {
    "fertiggerichte": ["Fertiggerichte"],
    "feinkost": ["Feinkost"],
    "vegetarisch": ["Vegetarisch"],
    "vegan": ["Vegan"],
    "glutenfrei": ["Glutenfrei"],
    "jougurth": ["Jogurt"],
    "jogurth": ["Jogurt"],
    "sauresahne": ["Saure Sahne"],
    "kurbiskernöl": ["Kürbiskernöl"],
    "früchtsäfte": ["Fruchtsäfte"],
    "fruchtsäfte": ["Fruchtsäfte"],
    "fruchtsaft": ["Fruchtsaft"],
    "pilze champignon": ["Pilze", "Champignon"],
    "säfte fruchtsäfte": ["Säfte", "Fruchtsäfte"],
    "brot berches": ["Brot", "Berches"],
    "laugengebäck brezeln": ["Laugengebäck", "Brezeln"],
    "konserven feinkost": ["Konserven", "Feinkost"],
    "pasta dinkel": ["Pasta", "Dinkel"],
    "cottage / hüttenkäse": ["Cottage", "Hüttenkäse"],
}

COMMON_TEXT_REPLACEMENTS = {
    "Wie·e": "Weiße",
    "Wei·e": "Weiße",
    "Wie·": "Weiß",
    "Me·mer": "Meßmer",
    "Jougurth": "Jogurt",
    "jogurth": "Jogurt",
    "BrälÇe": "Brûlée",
    "CafÇ": "Café",
    "SatÇ": "Saté",
    "Früchtsäfte": "Fruchtsäfte",
    "Marmelde": "Marmelade",
    "ôl": "öl",
    "Ôl": "Öl",
    "ôLE": "öle",
    "ôL": "öl",
    "·": "ß",
}

WEIRD_CHARS = ["�", "ô", "Ç", "·", "Ã", "Â"]


def fix_mojibake(text: str) -> str:
    if not text:
        return text

    candidates = [text]
    for enc in ("latin1", "cp1252"):
        try:
            candidates.append(text.encode(enc, errors="strict").decode("utf-8", errors="strict"))
        except Exception:
            pass

    def score(s: str) -> int:
        bad = sum(s.count(ch) for ch in WEIRD_CHARS)
        return bad

    return min(candidates, key=score)


def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = fix_mojibake(text)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\xa0", " ")
    text = text.replace("“", '"').replace("”", '"').replace("„", '"')
    text = text.replace("’", "'").replace("‘", "'").replace("_", "'")
    text = re.sub(r"\s+", " ", text).strip()

    for bad, good in COMMON_TEXT_REPLACEMENTS.items():
        text = text.replace(bad, good)

    return text


def clean_quotes_and_punct(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r'"{2,}', '"', text)
    text = re.sub(r"'{2,}", "'", text)
    text = re.sub(r'^\s*"+', "", text)
    text = re.sub(r'"+\s*$', "", text)
    text = re.sub(r"^\s*'+", "", text)
    text = re.sub(r"'+\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*[-,;:/]+\s*$", "", text).strip()
    return text


def smart_title_word(word: str) -> str:
    if not word:
        return word
    if word.upper() in ACRONYMS:
        return word.upper()
    if any(ch.isdigit() for ch in word):
        return word
    if len(word) <= 2 and word.isupper():
        return word
    return word[:1].upper() + word[1:].lower()


def smart_title_case(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return text

    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    if upper_ratio < 0.85:
        return text

    parts = re.split(r"(\s+|-|/|,|\(|\))", text)
    return "".join(
        smart_title_word(p) if not re.fullmatch(r"(\s+|-|/|,|\(|\))", p or "") else p
        for p in parts
    )


def normalize_for_match(text: str) -> str:
    text = normalize_text(text).lower()
    text = text.replace("ß", "ss")
    text = re.sub(r"[^a-z0-9äöü\s&/+.\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def dedupe_preserve(items: list[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def normalize_category_label(label: str) -> list[str]:
    label = clean_quotes_and_punct(label)
    if not label:
        return []

    alias = CATEGORY_ALIAS_MAP.get(label.lower())
    if alias:
        return alias

    return [label]


def merge_category_lists(base: list[str], extras: list[str]) -> list[str]:
    merged: list[str] = []
    for item in base + extras:
        merged.extend(normalize_category_label(item))
    return dedupe_preserve(merged)


def extract_size(name: str) -> tuple[str, str]:
    text = normalize_text(name)
    found_parts: list[str] = []

    changed = True
    while changed:
        changed = False
        for pattern in SIZE_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                part = clean_quotes_and_punct(match.group(0))
                if part and part not in found_parts:
                    found_parts.append(part)
                text = (text[:match.start()] + " " + text[match.end():]).strip()
                changed = True
                break

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*-\s*", "-", text)
    text = re.sub(r"\s*-\s*Trinkpack\b", "-Trinkpack", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[-,;:/]+\s*$", "", text).strip()

    size = " / ".join(found_parts).strip()
    return text, size


def clean_name(name: str) -> tuple[str, str]:
    name = clean_quotes_and_punct(name)
    if name.lower() in HEADER_LIKE_NAMES:
        return "", ""

    cleaned_name, size = extract_size(name)
    cleaned_name = re.sub(r"\s+\d+$", "", cleaned_name).strip()
    cleaned_name = re.sub(r"\s*-\s*", "-", cleaned_name)
    cleaned_name = re.sub(r"\s*,\s*", ", ", cleaned_name)
    cleaned_name = re.sub(r"\(\s+", "(", cleaned_name)
    cleaned_name = re.sub(r"\s+\)", ")", cleaned_name)
    cleaned_name = smart_title_case(cleaned_name)
    cleaned_name = re.sub(r"\b(Goldmais)\s+\1\b", r"\1", cleaned_name, flags=re.IGNORECASE)
    cleaned_name = clean_quotes_and_punct(cleaned_name)
    return cleaned_name, size


def extract_certificate_from_text(text: str) -> str:
    text = normalize_text(text)
    found: list[str] = []

    for suffix in sorted(CERT_SUFFIXES, key=len, reverse=True):
        if suffix in text and suffix not in found:
            found.append(suffix)

    if (
        "Rabbiner Garelik" in found
        and "Manchester Beit Din" in found
        and "Basel Kosher Commission" in found
    ):
        return "Rabbiner Garelik / Manchester Beit Din / Basel Kosher Commission"

    return " / ".join(found)


def clean_manufacturer(mfr: str) -> str:
    mfr = clean_quotes_and_punct(mfr)

    for suffix in sorted(CERT_SUFFIXES, key=len, reverse=True):
        mfr = mfr.replace(suffix, " ")

    for suffix in BRAND_SUFFIXES:
        if mfr.endswith(suffix):
            mfr = mfr[:-len(suffix)].strip().rstrip(",").strip()

    for suffix in LEGAL_SUFFIXES:
        mfr = re.sub(rf"\b{re.escape(suffix)}\b", "", mfr)

    mfr = re.sub(r"\s*,\s*,+", ", ", mfr)
    mfr = re.sub(r"\s+", " ", mfr).strip(" ,")
    mfr = clean_quotes_and_punct(mfr)
    return mfr


def make_lookup_key(name: str, manufacturer: str) -> str:
    return f"{name.lower().strip()}|{manufacturer.lower().strip()}"


def make_raw_lookup_key(raw_name: str, raw_manufacturer: str) -> str:
    return f"{normalize_text(raw_name).lower()}|{normalize_text(raw_manufacturer).lower()}"


def make_product_id(raw_name: str, raw_manufacturer: str) -> str:
    key = make_raw_lookup_key(raw_name, raw_manufacturer)
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


def canonical_product(product: dict) -> dict:
    allowed_fields = {
        "id",
        "source",
        "scope",
        "name",
        "display_name",
        "match_name",
        "manufacturer",
        "certificate",
        "categories",
        "dairy_status",
        "pessach",
        "size",
        "raw_name",
        "raw_manufacturer",
        "dairy_note",
        "pessach_note",
        "variants",
    }

    # remove explicitly known legacy fields first
    product = dict(product)
    product.pop("weitere_kategorien", None)
    product.pop("_extra_categories", None)

    out = {
        k: v for k, v in product.items()
        if k in allowed_fields and v not in (None, "", [], {})
    }

    out["source"] = "ORD"
    out.setdefault("scope", "product")

    if "name" in out:
        out["display_name"] = out["name"]
        out["match_name"] = normalize_for_match(out["name"])

    if "manufacturer" in out:
        out["manufacturer"] = clean_manufacturer(out["manufacturer"])

    if "categories" in out:
        out["categories"] = dedupe_preserve(out["categories"])

    return out


def load_existing(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        print("  ℹ No existing kosher_list.json found — fresh run.")
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        products = data.get("products", [])
        return {p["id"]: p for p in products if isinstance(p, dict) and "id" in p}
    except Exception as e:
        print(f"  ⚠ Could not load existing list: {e} — fresh run.")
        return {}


def fetch_categories(session: requests.Session) -> dict[int, str]:
    try:
        resp = session.get(BASE_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding or "utf-8"
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch category index: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    categories: dict[int, str] = {}

    for a in soup.select('a[href*="?cat="], a[href*="&cat="]'):
        href = a.get("href", "")
        full_url = urljoin(BASE_URL, href)
        qs = parse_qs(urlparse(full_url).query)
        cat_vals = qs.get("cat")
        if not cat_vals:
            continue

        try:
            cat_id = int(cat_vals[0])
        except (TypeError, ValueError):
            continue

        labels = normalize_category_label(a.get_text(" ", strip=True))
        if not labels:
            continue

        label = labels[0]
        if label.lower() in {"kategorie", "suche"}:
            continue

        categories[cat_id] = label

    if not categories:
        raise RuntimeError("No categories discovered on ORD site.")

    return categories


def parse_milchig_cell(cell) -> tuple[str, str]:
    if cell is None:
        return "unknown", ""

    note = clean_quotes_and_punct(cell.get_text(" ", strip=True))
    has_tick = cell.find("img") is not None
    note_lower = note.lower()

    if has_tick:
        return "milchig", note
    if "parve" in note_lower or "pareve" in note_lower or "nicht milchig" in note_lower:
        return "parve", note
    if "fleisch" in note_lower or "meat" in note_lower:
        return "fleischig", note
    if note:
        return "unknown", note
    return "unknown", ""


def parse_pessach_cell(cell) -> tuple[str, str]:
    if cell is None:
        return "unknown", ""

    note = clean_quotes_and_punct(cell.get_text(" ", strip=True))
    has_tick = cell.find("img") is not None
    note_lower = note.lower()

    if has_tick:
        return "kosher_lepessach", note
    if "nicht" in note_lower or "not" in note_lower:
        return "not_pessach", note
    if "pessach" in note_lower:
        return "kosher_lepessach", note
    if note:
        return "unknown", note
    return "unknown", ""


def split_additional_categories(text: str) -> list[str]:
    text = clean_quotes_and_punct(text)
    if not text:
        return []

    parts = re.split(r"\s{2,}|;|\|", text)
    out: list[str] = []

    for part in parts:
        part = part.strip(" ,")
        if not part:
            continue
        out.extend(normalize_category_label(part))

    return dedupe_preserve(out)


def parse_row(cells: list, previous_product: dict | None = None) -> tuple[dict | None, dict | None]:
    try:
        raw_name = clean_quotes_and_punct(cells[1].get_text(" ", strip=True)) if len(cells) > 1 else ""
        raw_manufacturer = clean_quotes_and_punct(cells[6].get_text(" ", strip=True)) if len(cells) > 6 else ""
        raw_extra_categories = clean_quotes_and_punct(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
        raw_certificate = clean_quotes_and_punct(cells[3].get_text(" ", strip=True)) if len(cells) > 3 else ""

        if not raw_name:
            return None, previous_product

        # variant rows
        if raw_name.startswith("(") and raw_name.endswith(")") and previous_product is not None:
            previous_product.setdefault("variants", [])
            if raw_name not in previous_product["variants"]:
                previous_product["variants"].append(raw_name)
            return None, previous_product

        name, size = clean_name(raw_name)
        if not name:
            return None, previous_product

        certs = []
        cert_from_mfr = extract_certificate_from_text(raw_manufacturer)
        if cert_from_mfr:
            certs.append(cert_from_mfr)

        cert_from_cert = extract_certificate_from_text(raw_certificate)
        if cert_from_cert:
            certs.append(cert_from_cert)

        certificate = " / ".join(dict.fromkeys([c for c in certs if c])).strip(" /")
        manufacturer = clean_manufacturer(raw_manufacturer)
        scope = "generic_rule" if manufacturer.lower() == "alle firmen" else "product"

        dairy_status, dairy_note = parse_milchig_cell(cells[4] if len(cells) > 4 else None)
        pessach_status, pessach_note = parse_pessach_cell(cells[5] if len(cells) > 5 else None)

        product = {
            "source": "ORD",
            "scope": scope,
            "name": name,
            "manufacturer": manufacturer,
            "certificate": certificate,
            "dairy_status": dairy_status,
            "pessach": pessach_status,
            "raw_name": raw_name,
            "raw_manufacturer": raw_manufacturer,
        }

        if size:
            product["size"] = size

        if raw_extra_categories:
            product["_extra_categories"] = split_additional_categories(raw_extra_categories)

        if dairy_note:
            if dairy_note.lower() in ("chalaw stam", "chemat stam", "chalav stam"):
                dairy_note = "Chalaw Stam"
            product["dairy_note"] = dairy_note

        if pessach_note:
            product["pessach_note"] = pessach_note

        return product, product

    except Exception as e:
        print(f"  ⚠ parse_row failed: {e}")
        return None, previous_product


def fetch_category(session: requests.Session, cat_id: int, cat_name: str) -> list[dict]:
    url = f"{BASE_URL}?cat={cat_id}&sortby=1"

    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding or "utf-8"
    except requests.RequestException as e:
        print(f"  ⚠ Failed to fetch cat {cat_id}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products: list[dict] = []

    table = soup.find("table")
    rows = table.find_all("tr") if table else soup.select("tr")

    previous_product: dict | None = None

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        product, previous_product = parse_row(cells, previous_product)
        if product:
            base_categories = [cat_name]
            extra_categories = product.pop("_extra_categories", [])
            product["categories"] = merge_category_lists(base_categories, extra_categories)
            products.append(product)

    return products


def scrape_all() -> tuple[list[dict], dict]:
    session = requests.Session()
    categories = fetch_categories(session)

    all_products: list[dict] = []
    seen: set[tuple[str, str]] = set()

    raw_stats = {
        "categories_found": len(categories),
        "categories_scraped": 0,
        "categories_empty": 0,
        "duplicates_removed": 0,
    }

    total = len(categories)

    for i, (cat_id, cat_name) in enumerate(sorted(categories.items()), 1):
        print(f"[{i:>3}/{total}] Fetching: {cat_name} (cat={cat_id})")
        products = fetch_category(session, cat_id, cat_name)

        for p in products:
            key = (p["raw_name"].lower(), p["raw_manufacturer"].lower())

            if key in seen:
                raw_stats["duplicates_removed"] += 1

                for existing in all_products:
                    existing_key = (
                        existing["raw_name"].lower(),
                        existing["raw_manufacturer"].lower(),
                    )
                    if existing_key == key:
                        existing["categories"] = merge_category_lists(
                            existing.get("categories", []),
                            p.get("categories", []),
                        )
                        if p.get("variants"):
                            existing["variants"] = dedupe_preserve(
                                existing.get("variants", []) + p["variants"]
                            )
                        if not existing.get("certificate") and p.get("certificate"):
                            existing["certificate"] = p["certificate"]
                        break
                continue

            seen.add(key)
            all_products.append(p)

        if products:
            raw_stats["categories_scraped"] += 1
        else:
            raw_stats["categories_empty"] += 1

    return all_products, raw_stats


def merge_products(scraped: list[dict], existing: dict[str, dict]) -> tuple[list[dict], dict]:
    stats = {"new": 0, "updated": 0, "unchanged": 0, "removed": 0}

    existing_by_raw_key: dict[str, dict] = {}
    existing_by_norm_key: dict[str, dict] = {}

    for p in existing.values():
        raw_name = p.get("raw_name", p.get("name", ""))
        raw_manufacturer = p.get("raw_manufacturer", p.get("manufacturer", ""))
        raw_key = make_raw_lookup_key(raw_name, raw_manufacturer)
        existing_by_raw_key[raw_key] = p

        norm_name = clean_name(p.get("name", ""))[0] if p.get("name") else ""
        norm_key = make_lookup_key(norm_name, clean_manufacturer(p.get("manufacturer", "")))
        existing_by_norm_key[norm_key] = p

    merged: list[dict] = []
    seen_ids: set[str] = set()

    for product in scraped:
        product_id = make_product_id(product["raw_name"], product["raw_manufacturer"])
        raw_key = make_raw_lookup_key(product["raw_name"], product["raw_manufacturer"])
        norm_key = make_lookup_key(product["name"], product["manufacturer"])

        existing_product = (
            existing.get(product_id)
            or existing_by_raw_key.get(raw_key)
            or existing_by_norm_key.get(norm_key)
        )

        if existing_product:
            merged_product = dict(existing_product)
            merged_product["id"] = product_id

            changed = False
            fields_to_update = [
                "source",
                "scope",
                "name",
                "manufacturer",
                "raw_name",
                "raw_manufacturer",
                "certificate",
                "dairy_status",
                "pessach",
                "dairy_note",
                "pessach_note",
                "size",
                "categories",
                "variants",
            ]

            for field in fields_to_update:
                new_val = product.get(field)
                old_val = existing_product.get(field)
                if new_val != old_val:
                    if new_val is not None:
                        merged_product[field] = new_val
                    elif field in merged_product:
                        del merged_product[field]
                    changed = True

            merged_product = canonical_product(merged_product)

            if changed:
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1
        else:
            merged_product = canonical_product({"id": product_id, **product})
            stats["new"] += 1

        seen_ids.add(product_id)
        merged.append(merged_product)

    for pid in existing:
        if pid not in seen_ids:
            stats["removed"] += 1

    return merged, stats


def build_manufacturer_index(products: list[dict]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for p in products:
        mfr = p["manufacturer"].lower().strip()
        index.setdefault(mfr, [])
        if p["id"] not in index[mfr]:
            index[mfr].append(p["id"])
    for mfr in index:
        index[mfr].sort()
    return index


def save_outputs(products: list[dict], scrape_stats: dict, merge_stats: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    version = now.strftime("%Y-%m-%d")

    products = [canonical_product(p) for p in products]
    products = sorted(
        products,
        key=lambda p: (
            p.get("manufacturer", "").lower(),
            p.get("name", "").lower(),
            p.get("size", "").lower() if p.get("size") else "",
        ),
    )

    kosher_list = {
        "version": version,
        "generated_at": now.isoformat(),
        "product_count": len(products),
        "products": products,
        "manufacturer_index": build_manufacturer_index(products),
    }

    list_path = os.path.join(OUTPUT_DIR, "kosher_list.json")
    with open(list_path, "w", encoding="utf-8") as f:
        json.dump(kosher_list, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Saved {len(products)} products → {list_path}")

    manifest = {
        "version": version,
        "generated_at": now.isoformat(),
        "product_count": len(products),
        "source": BASE_URL,
        "scrape_stats": scrape_stats,
        "merge_stats": merge_stats,
    }

    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved manifest      → {manifest_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("ORD Koscherliste Scraper")
    print("=" * 60)

    list_path = os.path.join(OUTPUT_DIR, "kosher_list.json")
    existing = load_existing(list_path)
    print(f"  Loaded {len(existing)} existing products\n")

    try:
        scraped, scrape_stats = scrape_all()
    except Exception as e:
        print(f"\n❌ Scrape failed: {e}")
        raise

    print(f"\nScraped {len(scraped)} unique products")
    print(f"Categories found   : {scrape_stats['categories_found']}")
    print(f"Categories scraped : {scrape_stats['categories_scraped']}")
    print(f"Categories empty   : {scrape_stats['categories_empty']}")
    print(f"Duplicates removed : {scrape_stats['duplicates_removed']}")

    merged, merge_stats = merge_products(scraped, existing)

    print("\nMerge results:")
    print(f"  New      : {merge_stats['new']}")
    print(f"  Updated  : {merge_stats['updated']}")
    print(f"  Unchanged: {merge_stats['unchanged']}")
    print(f"  Removed  : {merge_stats['removed']}")

    save_outputs(merged, scrape_stats, merge_stats)
