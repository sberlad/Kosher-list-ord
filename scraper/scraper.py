#!/usr/bin/env python3
"""
ORD Koscherliste Scraper

Scrapes https://koscherliste.ordonline.de/koscherliste/ and outputs:
  - kosher_list.json   (full product database, stable IDs, incremental updates)
  - manifest.json      (version info for app update checks)

Key improvements:
  - Categories discovered dynamically from the live site
  - Encoding normalized before parsing
  - Blank Milchig / Pessach cells treated as unknown, not negative
  - Raw source fields preserved for debugging
  - Merge logic includes fallback matching to reduce ID churn during cleanup migrations
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
    "Kof-K",
    "KLBD",
]

_BRAND_SUFFIXES = [
    "Balisto",
    "Bounty",
    "BRôLIO",
    "Vivani",
]


# ── Text normalization ────────────────────────────────────────────────────────

def normalize_text(s: str) -> str:
    """Normalize scraped text for stable parsing and matching."""
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def clean_name(name: str) -> str:
    """Normalize product name."""
    name = normalize_text(name)
    name = re.sub(r"\s*\d+$", "", name)
    return name.strip()


def clean_manufacturer(mfr: str) -> str:
    """Normalize manufacturer while trimming common suffix noise."""
    mfr = normalize_text(mfr)

    for suffix in _CERT_SUFFIXES:
        if mfr.endswith(suffix):
            mfr = mfr[:-len(suffix)].strip().rstrip(",").strip()
            break

    for suffix in _BRAND_SUFFIXES:
        if mfr.endswith(suffix):
            mfr = mfr[:-len(suffix)].strip().rstrip(",").strip()
            break

    mfr = re.sub(r"(\w)(Rabbiner\s)", r"\1 \2", mfr)
    return mfr.strip()


def make_lookup_key(name: str, manufacturer: str) -> str:
    """Stable normalized lookup key."""
    return f"{name.lower().strip()}|{manufacturer.lower().strip()}"


# ── Stable ID generation ──────────────────────────────────────────────────────

def make_product_id(name: str, manufacturer: str) -> str:
    """Generate a stable 12-char ID from normalized name + manufacturer."""
    key = make_lookup_key(name, manufacturer)
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

        label = normalize_text(a.get_text(" ", strip=True))
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

    note = normalize_text(cell.get_text(" ", strip=True))
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

    note = normalize_text(cell.get_text(" ", strip=True))
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


def parse_row(cells: list) -> dict | None:
    """Parse a product row into a normalized product dict."""
    try:
        raw_name = normalize_text(cells[1].get_text(" ", strip=True)) if len(cells) > 1 else ""
        raw_manufacturer = normalize_text(cells[6].get_text(" ", strip=True)) if len(cells) > 6 else ""
        weitere_kategorien = normalize_text(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
        certificate = normalize_text(cells[3].get_text(" ", strip=True)) if len(cells) > 3 else ""

        name = clean_name(raw_name)
        manufacturer = clean_manufacturer(raw_manufacturer)

        if not name:
            return None

        dairy_cell = cells[4] if len(cells) > 4 else None
        pessach_cell = cells[5] if len(cells) > 5 else None

        dairy_status, dairy_note = parse_milchig_cell(dairy_cell)
        pessach_status, pessach_note = parse_pessach_cell(pessach_cell)

        product = {
            "name": name,
            "manufacturer": manufacturer,
            "certificate": certificate,
            "weitere_kategorien": weitere_kategorien,
            "dairy_status": dairy_status,
            "pessach": pessach_status,
            "raw_name": raw_name,
            "raw_manufacturer": raw_manufacturer,
        }

        if dairy_note:
            if dairy_note.lower() in ("chalaw stam", "chemat stam", "chalav stam"):
                dairy_note = "Chalaw Stam"
            product["dairy_note"] = dairy_note

        if pessach_note:
            product["pessach_note"] = pessach_note

        return product

    except Exception as e:
        print(f"  ⚠ parse_row failed: {e}")
        return None


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_category(session: requests.Session, cat_id: int) -> list[dict]:
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

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        product = parse_row(cells)
        if product:
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
        products = fetch_category(session, cat_id)

        for p in products:
            key = (p["name"].lower(), p["manufacturer"].lower())

            if key in seen:
                raw_stats["duplicates_removed"] += 1

                for existing in all_products:
                    existing_key = (existing["name"].lower(), existing["manufacturer"].lower())
                    if existing_key == key:
                        if cat_name not in existing.get("categories", []):
                            existing.setdefault("categories", []).append(cat_name)
                        break

                continue

            seen.add(key)
            p["categories"] = [cat_name]
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
      1. Match by current generated ID
      2. Fallback by normalized key
      3. Fallback by raw key (to reduce churn during encoding cleanup migrations)
    """
    stats = {
        "new": 0,
        "updated": 0,
        "unchanged": 0,
        "removed": 0,
    }

    existing_by_norm_key: dict[str, dict] = {}
    existing_by_raw_key: dict[str, dict] = {}

    for p in existing.values():
        norm_key = make_lookup_key(
            clean_name(p.get("name", "")),
            clean_manufacturer(p.get("manufacturer", "")),
        )
        existing_by_norm_key[norm_key] = p

        raw_name = normalize_text(p.get("raw_name", p.get("name", "")))
        raw_manufacturer = normalize_text(p.get("raw_manufacturer", p.get("manufacturer", "")))
        raw_key = make_lookup_key(raw_name, raw_manufacturer)
        existing_by_raw_key[raw_key] = p

    merged: list[dict] = []
    seen_ids: set[str] = set()

    for product in scraped:
        product_id = make_product_id(product["name"], product["manufacturer"])
        norm_key = make_lookup_key(product["name"], product["manufacturer"])
        raw_key = make_lookup_key(
            product.get("raw_name", product["name"]),
            product.get("raw_manufacturer", product["manufacturer"]),
        )

        existing_product = (
            existing.get(product_id)
            or existing_by_norm_key.get(norm_key)
            or existing_by_raw_key.get(raw_key)
        )

        if existing_product:
            merged_product = dict(existing_product)
            merged_product["id"] = product_id

            changed = False
            fields_to_update = [
                "name",
                "manufacturer",
                "raw_name",
                "raw_manufacturer",
                "certificate",
                "weitere_kategorien",
                "dairy_status",
                "pessach",
                "dairy_note",
                "pessach_note",
                "categories",
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
