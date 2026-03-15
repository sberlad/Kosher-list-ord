#!/usr/bin/env python3
"""
ORD Koscherliste Scraper
Scrapes https://koscherliste.ordonline.de/koscherliste/ and outputs:
  - kosher_list.json   (full product database, stable IDs, incremental updates)
  - manifest.json      (version info for app update checks)

Run manually or via GitHub Actions on a schedule.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import hashlib
from datetime import datetime, timezone

BASE_URL = "https://koscherliste.ordonline.de/koscherliste/"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; KosherListBot/1.0; "
        "+https://github.com/sberlad/Kosher-list-ord)"
    )
}

CATEGORIES = {
    47: "Apfelessig, klar",
    48: "Apfelessig, naturtrüb",
    194: "Apfelsaft",
    49: "Aprikosenöl",
    50: "Arganöl",
    195: "Asia",
    1: "Aufstriche",
    51: "Avocadoöl",
    52: "Backmischungen",
    2: "Backwaren",
    54: "Backzutaten",
    197: "Berches",
    55: "Berliner",
    198: "Blaubeersaft",
    199: "Blütenhonig",
    3: "Bohnen",
    200: "Bohnenmehl",
    56: "Bonbons",
    57: "Branntweinessig",
    58: "Bratöl",
    201: "Brezeln",
    4: "Brot",
    5: "Brotaufstriche",
    60: "Brotbackmischungen",
    202: "Brotmischung",
    61: "Brötchen",
    62: "Bulgur",
    63: "Butter",
    6: "Cerealien",
    203: "Champignon",
    65: "Cornflakes",
    66: "Cottage / Hüttenkäse",
    7: "Couscous",
    68: "Creme",
    69: "Dauergebäck",
    8: "Dessert",
    205: "Dinkel",
    71: "Distel",
    72: "Distelöl",
    73: "Dressing",
    9: "Eis",
    238: "Eiscreme",
    206: "Eiskonfekt",
    10: "Erbsen",
    207: "Erbsenmehl",
    74: "Erdnussöl",
    208: "Ersatzkaffee",
    11: "Essig",
    209: "Exotic",
    210: "Feinkost",
    75: "Fertig Brot",
    76: "Fertiggerichte",
    12: "Fertigprodukte",
    78: "Fertigteige",
    13: "Fette",
    14: "Fisch",
    79: "Flakes",
    212: "Flocken, Getreide",
    15: "Freiverkäufliche Arzneimittel / Nahrungsergänzung",
    16: "Frischeprodukte",
    17: "Frischteig",
    80: "Frucht",
    214: "Fruchtjogurt",
    216: "Fruchtsaft",
    81: "Fruchtschnitten",
    82: "Fruchtsirup",
    83: "Fruchtzucker",
    84: "Fruktosesirup",
    85: "Früchte",
    18: "Früchtemus / Kompott",
    86: "Gelierzucker",
    19: "Gemüse",
    88: "Gemüseburger",
    237: "Gemüsekonserven",
    89: "Getränk",
    20: "Getränke",
    21: "Gewürze",
    91: "Gewürzmischungen",
    218: "Gewürzsauce",
    219: "Glutenfrei",
    92: "Gnocchi",
    220: "Grieß",
    93: "Grieß, Kleie, Leinsaat",
    94: "Haferkleie",
    95: "Hartweizen",
    96: "Haselnussöl",
    221: "Hefe",
    97: "Hering",
    98: "Himbeeressig",
    99: "Honig",
    222: "Honig-Senf",
    100: "Jogurt",
    102: "Kaffee",
    103: "Kaffeesahne",
    223: "Kartoffel",
    22: "Kartoffelprodukte",
    104: "Kaugummi",
    105: "Kekse",
    106: "Kernelöl",
    107: "Ketchup",
    23: "Kindernahrung",
    225: "Knoblauch",
    108: "Knusperbrot",
    109: "Knäckebrot",
    24: "Konserven",
    25: "Konvenienz",
    226: "Konzentrat",
    111: "Kornflakes",
    227: "Kornflocken",
    228: "Kräuter",
    229: "Kräuterbonbons",
    112: "Kräuteressig",
    230: "Kräuterlikör",
    113: "Kuchen",
    114: "Kürbiskernöl",
    231: "Kuvertüren",
    116: "Laugengebäck",
    117: "Leinsamen",
    118: "Leinöl",
    119: "Likör",
    26: "Linsen",
    120: "Lutscher",
    121: "Maiskeimöl",
    122: "Mandelöl",
    123: "Margarine",
    124: "Marmelade",
    126: "Marzipan",
    127: "Marzipanriegel",
    235: "Meersalz",
    27: "Mehl",
    129: "Meerrettich",
    131: "Milch",
    236: "Milchmixprodukte",
    28: "Milchprodukte",
    132: "Müsli",
    133: "Müsliriegel",
    29: "Nudeln",
    30: "Nudeln (Pasta)",
    134: "Nuss-Nougat-Creme",
    136: "Obst",
    137: "Obstkonserven",
    139: "Olivenöl",
    140: "Paprika",
    141: "Pasta",
    142: "Pesto",
    143: "Pflanzenöl",
    144: "Pilze",
    145: "Pistazienkernöl",
    146: "Pizzateig",
    147: "Pudding",
    148: "Puddingpulver",
    149: "Pulver",
    150: "Quark",
    151: "Rapsöl",
    32: "Reis",
    33: "Reisgebäck",
    152: "Reismehl",
    153: "Röstzwiebeln",
    154: "Saft",
    155: "Salatöl",
    34: "Salz",
    157: "Salzgebäck",
    35: "Saucen",
    158: "Saure Sahne",
    159: "Schmand",
    160: "Schoko-Dessert",
    161: "Schokolade",
    162: "Schwarzkümmelöl",
    163: "Sesamöl",
    164: "Sirup",
    165: "Smoothies",
    166: "Softdrinks",
    36: "Soja",
    168: "Sojaöl",
    169: "Sonnenblumenöl",
    37: "Spirituosen",
    38: "Stärke",
    39: "Suppen",
    40: "Süßwaren",
    173: "Säfte",
    174: "Tee",
    175: "Thunfisch",
    42: "Tiefkühl",
    176: "Tiefkühlkost",
    177: "Toffees",
    178: "Tomate",
    179: "Tomaten",
    180: "Tomatenkonzentrat",
    181: "Traubenkernöl",
    182: "Traubenzucker",
    183: "Vegan",
    184: "Vegetarisch",
    43: "Vegetarische Wurst",
    44: "Vegetarischer Wurstersatz",
    185: "Vodka",
    186: "Walnusskernöl",
    187: "Walnussöl",
    188: "Weizenkeimöl",
    189: "Weizenkleie",
    190: "Wildrosenöl",
    191: "Zedernnussöl",
    45: "Zucker",
    46: "Zucker / Süßmittel",
    193: "Zwieback",
    31: "Öl",
}


# ── Stable ID generation ──────────────────────────────────────────────────────

def make_product_id(name: str, manufacturer: str) -> str:
    """Generate a stable 12-char ID from name + manufacturer.
    Deterministic: same input always produces same ID.
    """
    key = f"{name.lower().strip()}|{manufacturer.lower().strip()}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


# ── Load existing data ────────────────────────────────────────────────────────

def load_existing(path: str) -> dict[str, dict]:
    """Load existing kosher_list.json and return a dict of id → product.
    Returns empty dict if file doesn't exist or is malformed.
    """
    if not os.path.exists(path):
        print("  ℹ No existing kosher_list.json found — fresh run.")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        products = data.get("products", [])
        # Index by ID for fast lookup
        return {p["id"]: p for p in products if "id" in p}
    except Exception as e:
        print(f"  ⚠ Could not load existing list: {e} — fresh run.")
        return {}


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_category(session: requests.Session, cat_id: int) -> list[dict]:
    """Fetch all products for a given category ID."""
    url = f"{BASE_URL}?cat={cat_id}&sortby=1"
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ⚠ Failed to fetch cat {cat_id}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []

    table = soup.find("table")
    if not table:
        rows = soup.select("tr.product-row, tr[class*='item'], .koscherliste-item")
    else:
        rows = table.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        product = parse_row(cells)
        if product:
            products.append(product)

    return products


def parse_row(cells: list) -> dict | None:
    """Parse a table row into a product dict."""
    try:
        name = clean_name(cells[1].get_text(strip=True)) if len(cells) > 1 else ""
        manufacturer = clean_manufacturer(cells[6].get_text(strip=True)) if len(cells) > 6 else ""
        weitere_kategorien = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        certificate = cells[3].get_text(strip=True) if len(cells) > 3 else ""

        if not name:
            return None

        milchig_cell = cells[4] if len(cells) > 4 else None
        dairy_status, dairy_note = parse_milchig_cell(milchig_cell)

        pessach_cell = cells[5] if len(cells) > 5 else None
        pessach_status, pessach_note = parse_pessach_cell(pessach_cell)

        product = {
            "name": name,
            "manufacturer": manufacturer,
            "certificate": certificate,
            "weitere_kategorien": weitere_kategorien,
            "dairy_status": dairy_status,
            "pessach": pessach_status,
        }

        if dairy_note:
            if dairy_note.lower() in ("chalaw stam", "chemat stam", "chalav stam"):
                dairy_note = "Chalaw Stam"
            product["dairy_note"] = dairy_note
        if pessach_note:
            product["pessach_note"] = pessach_note

        return product

    except Exception:
        return None


def parse_milchig_cell(cell) -> tuple[str, str]:
    if cell is None:
        return "unknown", ""
    has_tick = cell.find("img") is not None
    note = cell.get_text(strip=True)
    if has_tick:
        return "milchig", note
    elif note:
        note_lower = note.lower()
        if "parve" in note_lower or "pareve" in note_lower:
            return "parve", ""
        if "fleisch" in note_lower or "meat" in note_lower:
            return "fleischig", note
        return "milchig", note
    else:
        return "parve", ""


def parse_pessach_cell(cell) -> tuple[str, str]:
    if cell is None:
        return "unknown", ""
    has_tick = cell.find("img") is not None
    note = cell.get_text(strip=True)
    if has_tick:
        return "kosher_lepessach", note
    elif note:
        note_lower = note.lower()
        if "nicht" in note_lower or "not" in note_lower:
            return "not_pessach", note
        return "kosher_lepessach", note
    else:
        return "not_pessach", ""


_CERT_SUFFIXES = [
    "Rabbiner Tuvia Hod Hochwald", "Rabbiner Jona Pawel",
    "Rabbiner  Meir Hord", "Rabbiner Meir Hord",
    "Kof-K", "KLBD",
]
_BRAND_SUFFIXES = ["Balisto", "Bounty", "BRôLIO", "Vivani"]


def clean_name(name: str) -> str:
    name = name.replace("·", "ß")
    name = re.sub(r"\s*\d+$", "", name).strip()
    return name


def clean_manufacturer(mfr: str) -> str:
    mfr = mfr.replace("·", "ß")
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


# ── Merge logic ───────────────────────────────────────────────────────────────

def merge_products(scraped: list[dict], existing: dict[str, dict]) -> tuple[list[dict], dict]:
    """Merge freshly scraped products with existing data.
    - Preserves IDs for known products
    - Assigns new IDs for new products
    - Updates changed fields
    - Tracks stats
    """
    stats = {
        "new": 0,
        "updated": 0,
        "unchanged": 0,
        "removed": 0,
    }

    # Build lookup of existing products by (name, manufacturer) key
    # in case IDs aren't yet assigned (first run after adding ID support)
    existing_by_key: dict[str, dict] = {}
    for p in existing.values():
        key = f"{p['name'].lower().strip()}|{p['manufacturer'].lower().strip()}"
        existing_by_key[key] = p

    merged: list[dict] = []
    seen_ids: set[str] = set()

    for product in scraped:
        product_id = make_product_id(product["name"], product["manufacturer"])
        key = f"{product['name'].lower().strip()}|{product['manufacturer'].lower().strip()}"

        # Look up existing by ID first, then by key (for migration)
        existing_product = existing.get(product_id) or existing_by_key.get(key)

        if existing_product:
            # Product exists — check for changes
            merged_product = {**existing_product}  # start with existing
            merged_product["id"] = product_id  # ensure ID is set

            changed = False
            fields_to_update = [
                "certificate", "weitere_kategorien", "dairy_status",
                "pessach", "dairy_note", "pessach_note", "categories"
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
            # New product
            merged_product = {"id": product_id, **product}
            stats["new"] += 1

        seen_ids.add(product_id)
        merged.append(merged_product)

    # Count removed products (in existing but not in new scrape)
    for pid in existing:
        if pid not in seen_ids:
            stats["removed"] += 1
            # Note: we don't carry them forward — they're gone from the list

    return merged, stats


def scrape_all() -> tuple[list[dict], dict]:
    """Scrape every category and return (products, stats)."""
    session = requests.Session()
    all_products: list[dict] = []
    seen: set[tuple] = set()
    raw_stats = {"categories_scraped": 0, "categories_empty": 0, "duplicates_removed": 0}

    total = len(CATEGORIES)
    for i, (cat_id, cat_name) in enumerate(CATEGORIES.items(), 1):
        print(f"[{i:>3}/{total}] Fetching: {cat_name} (cat={cat_id})")
        products = fetch_category(session, cat_id)

        for p in products:
            key = (p["name"].lower(), p["manufacturer"].lower())
            if key in seen:
                raw_stats["duplicates_removed"] += 1
                # Add category to existing entry
                for existing in all_products:
                    if (existing["name"].lower(), existing["manufacturer"].lower()) == key:
                        if cat_name not in existing.get("categories", []):
                            existing.setdefault("categories", []).append(cat_name)
                continue
            seen.add(key)
            p["categories"] = [cat_name]
            all_products.append(p)

        if products:
            raw_stats["categories_scraped"] += 1
        else:
            raw_stats["categories_empty"] += 1

    return all_products, raw_stats


def build_manufacturer_index(products: list[dict]) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for p in products:
        mfr = p["manufacturer"].lower().strip()
        index.setdefault(mfr, [])
        if p["name"] not in index[mfr]:
            index[mfr].append(p["name"])
    return index


def save_outputs(products: list[dict], scrape_stats: dict, merge_stats: dict) -> None:
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
        "source": "https://koscherliste.ordonline.de/koscherliste/",
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

    scraped, scrape_stats = scrape_all()
    print(f"\nScraped {len(scraped)} unique products")
    print(f"Categories scraped : {scrape_stats['categories_scraped']}")
    print(f"Categories empty   : {scrape_stats['categories_empty']}")
    print(f"Duplicates removed : {scrape_stats['duplicates_removed']}")

    merged, merge_stats = merge_products(scraped, existing)
    print(f"\nMerge results:")
    print(f"  New      : {merge_stats['new']}")
    print(f"  Updated  : {merge_stats['updated']}")
    print(f"  Unchanged: {merge_stats['unchanged']}")
    print(f"  Removed  : {merge_stats['removed']}")

    save_outputs(merged, scrape_stats, merge_stats)
```

Key changes from the original:
- `make_product_id()` - stable hash ID per product
- `load_existing()` - loads current JSON before scraping
- `merge_products()` - preserves IDs, updates only changed fields, tracks new/updated/removed
- `save_outputs()` - now includes merge stats in manifest
- Duplicate category tagging logic cleaned up (was slightly broken before)

Paste it in, save, then run it once manually to assign IDs to all existing products:
```
python scraper/scraper.py