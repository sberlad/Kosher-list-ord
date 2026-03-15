#!/usr/bin/env python3
"""
ORD Koscherliste Scraper

Scrapes https://koscherliste.ordonline.de/koscherliste/ and outputs:
  - kosher_list.json   (full product database, stable IDs, incremental updates)
  - manifest.json      (version info for app update checks)

Improvements in this version:
  - Categories discovered dynamically from the live site
  - Encoding normalized before parsing
  - Blank Milchig / Pessach cells treated as unknown, not negative
  - Raw source fields preserved for debugging
  - IDs generated from raw source fields for better long-term stability
  - Variant rows appended to previous product instead of becoming fake products
  - Size/weight text split out into a dedicated size field where possible
  - Manufacturer certificates extracted before cleaning manufacturer text
  - weitere_kategorien removed from output; canonical categories only
  - Optional legal suffix cleanup for manufacturer normalization
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

_CERT_SUFFIXES = [
    "Rabbiner Tuvia Hod Hochwald",
    "Rabbiner Jona Pawel",
    "Rabbiner  Meir Hord",
    "Rabbiner Meir Hord",
    "Rabbiner Jaron Engelmayer",
    "Rabbiner Avichai Apel",
    "Rabbiner Mark (Mordechai) Pavlovsky",
    "Rabbiner Moshe Flomenmann",
    "Rabbiner Zsolt Balla",
    "Rabbiner Dov Levy Barsilay",
    "Rabbiner Hazan",
    "Rabbiner Garelik",
    "Rabbiner P. Padwa",
    "Rabbiner Israel Meir Levinger",
    "London Beit Din",
    "Manchester Kosher",
    "Manchester Beit Din",
    "Basel Kosher Commission",
    "K Meschulasch Oberrabbiner Liebermann",
    "Kof-K",
    "KLBD",
]

_BRAND_SUFFIXES = [
    "Balisto",
    "Bounty",
    "BRôLIO",
    "Vivani",
]

_LEGAL_SUFFIXES = [
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
    "S.A.",
    "S.R.L.",
    "S.p.A.",
]

_SIZE_PATTERNS = [
    r"\b\d+\s?(?:x\s?)?\d+[,.]?\d*\s?(?:g|kg|ml|l)\b",
    r"\b\d+[,.]?\d*\s?(?:g|kg|ml|l)\b",
    r"\bGastro\s?\d+[,.]?\d*\s?(?:g|kg|ml|l)\b",
]


# ── Text normalization ────────────────────────────────────────────────────────

def normalize_text(s: str) -> str:
    """Normalize scraped text for stable parsing and matching."""
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\xa0", " ")
    s = s.replace("“", '"').replace("”", '"').replace("„", '"')
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_quotes_and_punct(s: str) -> str:
    """Clean repeated quotes and trailing punctuation noise."""
    s = normalize_text(s)
    s = re.sub(r'"{2,}', '"', s)
    s = re.sub(r"'{2,}", "'", s)
    s = re.sub(r'^\s*"+', "", s)
    s = re.sub(r'"+\s*$', "", s)
    s = re.sub(r"^\s*'+", "", s)
    s = re.sub(r"'+\s*$", "", s)
    s = re.sub(r"\s*[-,;:/]+\s*$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_size(name: str) -> tuple[str, str]:
    """
    Extract a likely size/packaging fragment from a product name.
    Returns (name_without_size, size).
    """
    text = normalize_text(name)
    found_parts: list[str] = []

    for pattern in _SIZE_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            for m in matches:
                if m not in found_parts:
                    found_parts.append(m)
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s*[-,;:/]+\s*$", "", text).strip()

    size = " / ".join(found_parts).strip()
    return text, size


def clean_name(name: str) -> tuple[str, str]:
    """Normalize product name and extract size if possible."""
    name = clean_quotes_and_punct(name)

    # Remove obvious placeholder header rows
    if name.lower() in {"artikelbezeichnung", "produkt", "produktbezeichnung"}:
        return "", ""

    cleaned_name, size = extract_size(name)

    # remove trailing bare numbers only if they are left hanging
    cleaned_name = re.sub(r"\s+\d+$", "", cleaned_name).strip()

    # normalize weird residual punctuation
    cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip()
    cleaned_name = re.sub(r"\s*[-,;:/]+\s*$", "", cleaned_name).strip()

    return cleaned_name, size


def extract_certificate_from_text(text: str) -> str:
    """Extract certificate/hechsher references from free text."""
    text = normalize_text(text)

    found: list[str] = []
    for suffix in _CERT_SUFFIXES:
        if suffix in text and suffix not in found:
            found.append(suffix)

    # Prefer longest / richest info first
    found = sorted(found, key=len, reverse=True)
    return " / ".join(found)


def clean_manufacturer(mfr: str) -> str:
    """Normalize manufacturer while trimming common suffix noise."""
    mfr = clean_quotes_and_punct(mfr)

    # Remove certifier text from manufacturer after extracting elsewhere
    for suffix in sorted(_CERT_SUFFIXES, key=len, reverse=True):
        mfr = mfr.replace(suffix, " ")

    for suffix in _BRAND_SUFFIXES:
        if mfr.endswith(suffix):
            mfr = mfr[:-len(suffix)].strip().rstrip(",").strip()

    mfr = re.sub(r"(\w)(Rabbiner\s)", r"\1 \2", mfr)

    # Optional legal suffix cleanup
    for suffix in _LEGAL_SUFFIXES:
        mfr = re.sub(rf"\b{re.escape(suffix)}\b", "", mfr)

    mfr = re.sub(r"\s*,\s*,+", ", ", mfr)
    mfr = re.sub(r"\s+", " ", mfr).strip(" ,")
    return mfr.strip()


def make_lookup_key(name: str, manufacturer: str) -> str:
    """Stable normalized lookup key."""
    return f"{name.lower().strip()}|{manufacturer.lower().strip()}"


def make_raw_lookup_key(raw_name: str, raw_manufacturer: str) -> str:
    """Stable raw lookup key."""
    return f"{normalize_text(raw_name).lower()}|{normalize_text(raw_manufacturer).lower()}"


# ── Stable ID generation ──────────────────────────────────────────────────────

def make_product_id(raw_name: str, raw_manufacturer: str) -> str:
    """Generate a stable 12-char ID from raw source name + manufacturer."""
    key = make_raw_lookup_key(raw_name, raw_manufacturer)
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:12]


# ── Load existing data ────────────────────────────────────────────────────────

def load_existing(path: str) -> dict[str, dict]:
    """Load existing kosher_list.json and return a dict of id → product."""
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


# ── Category discovery ────────────────────────────────────────────────────────

def fetch_categories(session: requests.Session) -> dict[int, str]:
    """Discover category IDs and labels dynamically from the live site."""
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

        label = clean_quotes_and_punct(a.get_text(" ", strip=True))
        if not label:
            continue
        if label.lower() in {"kategorie", "suche"}:
            continue

        categories[cat_id] = label

    if not categories:
        raise RuntimeError("No categories discovered on ORD site.")

    return categories


# ── Cell parsing ──────────────────────────────────────────────────────────────

def parse_milchig_cell(cell) -> tuple[str, str]:
    """
    Parse dairy cell.

    Returns:
      - status: milchig | parve | fleischig | unknown
      - note: raw/normalized note text
    """
    if cell is None:
        return "unknown", ""

    note = clean_quotes_and_punct(cell.get_text(" ", strip=True))
    has_tick = cell.find("img") is not None

    if has_tick:
        return "milchig", note

    note_lower = note.lower()

    if "parve" in note_lower or "pareve" in note_lower or "nicht milchig" in note_lower:
        return "parve", note
    if "fleisch" in note_lower or "meat" in note_lower:
        return "fleischig", note
    if note:
        return "unknown", note

    return "unknown", ""


def parse_pessach_cell(cell) -> tuple[str, str]:
    """
    Parse Pessach cell.

    Returns:
      - status: kosher_lepessach | not_pessach | unknown
      - note: raw/normalized note text
    """
    if cell is None:
        return "unknown", ""

    note = clean_quotes_and_punct(cell.get_text(" ", strip=True))
    has_tick = cell.find("img") is not None

    if has_tick:
        return "kosher_lepessach", note

    note_lower = note.lower()

    if "nicht" in note_lower or "not" in note_lower:
        return "not_pessach", note
    if "pessach" in note_lower:
        return "kosher_lepessach", note
    if note:
        return "unknown", note

    return "unknown", ""


def split_additional_categories(text: str) -> list[str]:
    """Split additional categories heuristically."""
    text = clean_quotes_and_punct(text)
    if not text:
        return []

    # Split only on clear separators, not commas inside category names
    parts = re.split(r"\s{2,}|/|;|\|", text)
    out: list[str] = []

    for part in parts:
        part = part.strip(" ,")
        if not part:
            continue

        # If still a long chain without separators, try a soft split on capitalized transitions
        if len(part) > 35 and " " in part:
            out.append(part)
        else:
            out.append(part)

    return [p for p in out if p]


def merge_category_lists(base: list[str], extras: list[str]) -> list[str]:
    """Merge category labels while preserving order and uniqueness."""
    seen = set()
    merged = []

    for item in base + extras:
        item = clean_quotes_and_punct(item)
        if not item:
            continue
        key = item.lower()
        if key not in seen:
            seen.add(key)
            merged.append(item)

    return merged


# ── Row parsing ───────────────────────────────────────────────────────────────

def parse_row(cells: list, previous_product: dict | None = None) -> tuple[dict | None, dict | None]:
    """
    Parse a product row into a normalized product dict.

    Returns:
      (product_or_none, updated_previous_product)

    Variant rows are appended to previous_product["variants"] and do not create
    a new product record.
    """
    try:
        raw_name = clean_quotes_and_punct(cells[1].get_text(" ", strip=True)) if len(cells) > 1 else ""
        raw_manufacturer = clean_quotes_and_punct(cells[6].get_text(" ", strip=True)) if len(cells) > 6 else ""
        raw_extra_categories = clean_quotes_and_punct(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
        raw_certificate = clean_quotes_and_punct(cells[3].get_text(" ", strip=True)) if len(cells) > 3 else ""

        if not raw_name:
            return None, previous_product

        # Variant row: attach to previous product instead of creating a fake product.
        if raw_name.startswith("(") and previous_product is not None:
            previous_product.setdefault("variants", [])
            if raw_name not in previous_product["variants"]:
                previous_product["variants"].append(raw_name)
            return None, previous_product

        name, size = clean_name(raw_name)
        if not name:
            return None, previous_product

        extracted_certs = []
        if raw_certificate:
            extracted_certs.append(raw_certificate)

        cert_from_mfr = extract_certificate_from_text(raw_manufacturer)
        if cert_from_mfr:
            extracted_certs.append(cert_from_mfr)

        certificate = " / ".join(
            dict.fromkeys([c for c in extracted_certs if c])
        ).strip(" /")

        manufacturer = clean_manufacturer(raw_manufacturer)

        dairy_cell = cells[4] if len(cells) > 4 else None
        pessach_cell = cells[5] if len(cells) > 5 else None

        dairy_status, dairy_note = parse_milchig_cell(dairy_cell)
        pessach_status, pessach_note = parse_pessach_cell(pessach_cell)

        product = {
            "source": "ORD",
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


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_category(session: requests.Session, cat_id: int, cat_name: str) -> list[dict]:
    """Fetch all products for a given category ID."""
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
    """Scrape every discovered category and return (products, scrape_stats)."""
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
                            existing["variants"] = list(
                                dict.fromkeys(existing.get("variants", []) + p["variants"])
                            )

                        # If duplicate row has cert info we lacked, keep it
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


# ── Merge logic ───────────────────────────────────────────────────────────────

def merge_products(scraped: list[dict], existing: dict[str, dict]) -> tuple[list[dict], dict]:
    """
    Merge freshly scraped products with existing data.

    Strategy:
      1. Match by current raw-based ID
      2. Fallback by raw key
      3. Fallback by normalized key
    """
    stats = {
        "new": 0,
        "updated": 0,
        "unchanged": 0,
        "removed": 0,
    }

    existing_by_raw_key: dict[str, dict] = {}
    existing_by_norm_key: dict[str, dict] = {}

    for p in existing.values():
        raw_name = p.get("raw_name", p.get("name", ""))
        raw_manufacturer = p.get("raw_manufacturer", p.get("manufacturer", ""))
        raw_key = make_raw_lookup_key(raw_name, raw_manufacturer)
        existing_by_raw_key[raw_key] = p

        norm_key = make_lookup_key(
            clean_name(p.get("name", ""))[0] if p.get("name") else "",
            clean_manufacturer(p.get("manufacturer", "")),
        )
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

            if changed:
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1
        else:
            merged_product = {"id": product_id, **product}
            stats["new"] += 1

        seen_ids.add(product_id)
        merged.append(merged_product)

    for pid in existing:
        if pid not in seen_ids:
            stats["removed"] += 1

    return merged, stats


# ── Output helpers ────────────────────────────────────────────────────────────

def build_manufacturer_index(products: list[dict]) -> dict[str, list[str]]:
    """Build simple manufacturer → product names index."""
    index: dict[str, list[str]] = {}

    for p in products:
        mfr = p["manufacturer"].lower().strip()
        index.setdefault(mfr, [])

        if p["name"] not in index[mfr]:
            index[mfr].append(p["name"])

    return index


def save_outputs(products: list[dict], scrape_stats: dict, merge_stats: dict) -> None:
    """Write kosher_list.json and manifest.json."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    version = now.strftime("%Y-%m-%d")

    # Stable, readable ordering helps diffs
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


# ── Main ──────────────────────────────────────────────────────────────────────

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
