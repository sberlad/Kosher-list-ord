#!/usr/bin/env python3
"""
ORD Koscherliste Scraper
Scrapes https://koscherliste.ordonline.de/koscherliste/ and outputs:
  - kosher_list.json   (full product database)
  - manifest.json      (version info for app update checks)

Run manually or via GitHub Actions on a schedule.
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime, timezone

BASE_URL = "https://koscherliste.ordonline.de/koscherliste/"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; KosherListBot/1.0; "
        "+https://github.com/your-org/kosher-list-app)"
    )
}

# ── Category IDs extracted from the main page ────────────────────────────────
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

    # The site renders products in a table. Each row contains:
    # product name, manufacturer, certificate, milchig/parve flag, Pessach flag
    table = soup.find("table")
    if not table:
        # Try alternative: products may be in divs/lists depending on page
        rows = soup.select("tr.product-row, tr[class*='item'], .koscherliste-item")
    else:
        rows = table.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue  # Skip header rows or empty rows

        product = parse_row(cells)
        if product:
            products.append(product)

    return products


def parse_row(cells: list) -> dict | None:
    """Parse a table row into a product dict."""
    try:
        # Column order observed on site:
        # 0: Produkt (product name)
        # 1: Hersteller (manufacturer)
        # 2: Zertifikat (certificate/authority)
        # 3: Milchig / Parve / Nicht milchig
        # 4: Koscher lePessach flags
        # (column count varies — be defensive)

        name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
        manufacturer = cells[2].get_text(strip=True) if len(cells) > 2 else ""
        certificate = cells[3].get_text(strip=True) if len(cells) > 3 else ""
        milchig_raw = cells[4].get_text(strip=True) if len(cells) > 4 else ""
        pessach_raw = cells[5].get_text(strip=True) if len(cells) > 5 else ""

        if not name or not manufacturer:
            return None

        # Normalise dairy status
        milchig = normalise_dairy(milchig_raw)

        # Normalise Pessach status
        pessach = normalise_pessach(pessach_raw)

        return {
            "name": name,
            "manufacturer": manufacturer,
            "certificate": certificate,
            "dairy_status": milchig,       # "milchig" | "parve" | "fleischig" | "unknown"
            "pessach": pessach,             # "kosher_lepessach" | "not_pessach" | "suitable" | "unknown"
        }
    except Exception:
        return None


def normalise_dairy(raw: str) -> str:
    raw_lower = raw.lower()
    if "milchig" in raw_lower or "dairy" in raw_lower:
        return "milchig"
    if "parve" in raw_lower or "pareve" in raw_lower:
        return "parve"
    if "fleisch" in raw_lower or "meat" in raw_lower:
        return "fleischig"
    return "unknown"


def normalise_pessach(raw: str) -> str:
    raw_lower = raw.lower()
    if "le pessach" in raw_lower or "lepessach" in raw_lower:
        return "kosher_lepessach"
    if "geeignet" in raw_lower:
        return "suitable"
    if "nicht" in raw_lower:
        return "not_pessach"
    return "unknown"


def scrape_all() -> tuple[list[dict], dict]:
    """Scrape every category and return (products, stats)."""
    session = requests.Session()
    all_products: list[dict] = []
    seen: set[tuple] = set()  # Deduplicate by (name, manufacturer)
    stats = {"categories_scraped": 0, "categories_empty": 0, "duplicates_removed": 0}

    total = len(CATEGORIES)
    for i, (cat_id, cat_name) in enumerate(CATEGORIES.items(), 1):
        print(f"[{i:>3}/{total}] Fetching: {cat_name} (cat={cat_id})")
        products = fetch_category(session, cat_id)

        for p in products:
            key = (p["name"].lower(), p["manufacturer"].lower())
            if key in seen:
                stats["duplicates_removed"] += 1
                continue
            seen.add(key)
            p["categories"] = [cat_name]
            all_products.append(p)

        # Tag already-seen products with additional categories
        # (a product can appear under multiple categories)
        if products:
            stats["categories_scraped"] += 1
            # Add category to existing products if they show up again
            for p in products:
                key = (p["name"].lower(), p["manufacturer"].lower())
                for existing in all_products:
                    ekey = (existing["name"].lower(), existing["manufacturer"].lower())
                    if ekey == key and cat_name not in existing["categories"]:
                        existing["categories"].append(cat_name)
        else:
            stats["categories_empty"] += 1

    return all_products, stats


def build_manufacturer_index(products: list[dict]) -> dict[str, list[str]]:
    """Build a normalised manufacturer → [product names] index for fuzzy matching."""
    index: dict[str, list[str]] = {}
    for p in products:
        mfr = p["manufacturer"].lower().strip()
        index.setdefault(mfr, [])
        if p["name"] not in index[mfr]:
            index[mfr].append(p["name"])
    return index


def save_outputs(products: list[dict], stats: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    version = now.strftime("%Y-%m-%d")

    # ── kosher_list.json ──────────────────────────────────────────────────────
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

    # ── manifest.json ─────────────────────────────────────────────────────────
    manifest = {
        "version": version,
        "generated_at": now.isoformat(),
        "product_count": len(products),
        "source": "https://koscherliste.ordonline.de/koscherliste/",
        "stats": stats,
    }
    manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved manifest      → {manifest_path}")


if __name__ == "__main__":
    print("=" * 60)
    print("ORD Koscherliste Scraper")
    print("=" * 60)
    products, stats = scrape_all()
    print(f"\nTotal unique products : {len(products)}")
    print(f"Categories scraped    : {stats['categories_scraped']}")
    print(f"Categories empty      : {stats['categories_empty']}")
    print(f"Duplicates removed    : {stats['duplicates_removed']}")
    save_outputs(products, stats)
