# Kosher Scanner

**Tech stack:** React Native (Expo) · TypeScript · Python · GitHub Actions · Supabase · Open Food Facts API

> **Project goal:** To explore AI-assisted software development workflows while building a practical tool for kosher consumers in Germany.

An iOS & Android app that scans product barcodes and checks them against the ORD (Orthodoxe Rabbinerkonferenz Deutschland) Koscherliste.

---

## How it works

```
Barcode scan
│
▼
Trusted barcode cache (Supabase)   ← checked first; crowd-sourced confirmed matches
│  hit → instant result
│
▼
Open Food Facts API                ← barcode → product name + brand (free, no key)
│  not found → "unknown"
│
▼
ORD kosher_list.json               ← cached on device, fetched from GitHub, refreshed daily
(name + manufacturer lookup — 6 priority tiers)
│
├─ Exact product match        → ✅  Kosher (ORD certified)
├─ Fuzzy / manufacturer match → ⚠️  Possible match (user confirmation requested)
├─ Manufacturer rule match    → 🏷  Brand has a standing ORD rule for this product type
├─ Generic rule match         → 💧  All-producer ORD rule (e.g. "alle Firmen – Butter")
└─ No match                   → ❌  Not on ORD list
```

No backend server is needed for lookups. All kosher list data is served as static JSON from GitHub. Confirmed barcode matches are stored in Supabase (free tier) and shared across users.

---

## Repository structure

```
Kosher-list-ord/
├── scraper/
│   ├── scraper.py              # Scrapes ORD Koscherliste; classifies records by type
│   ├── diff_utils.py           # Content hashing + product diff helpers
│   ├── snapshot_utils.py       # Saves versioned snapshots on content change
│   ├── validate_kosher_list.py # Data-quality checks (duplicates, weird chars, etc.)
│   └── output/
│       ├── kosher_list.json    # Full product + rule database (stable IDs, incremental)
│       └── manifest.json       # Version, hash, scrape stats
│
├── .github/
│   └── workflows/
│       └── scrape.yml          # GitHub Actions — runs scraper every Monday 06:00 UTC
│
└── KosherScanner/              # React Native (Expo) app
    ├── app/
    │   ├── _layout.tsx
    │   └── index.tsx           # Camera + barcode scan UI, result caching
    ├── services/
    │   ├── KosherService.ts    # Core lookup logic: matching, fuzzy scoring, rule eval
    │   ├── OpenFoodFacts.ts    # Open Food Facts API integration
    │   └── BarcodeConfirmationApi.ts  # Supabase trusted-barcode read/write
    └── components/
        └── ResultModal.tsx     # Animated result sheet, distinct UI per match type
```

---

## Data pipeline

### Scraper (`scraper/scraper.py`)

- Scrapes [ORD Koscherliste](https://koscherliste.ordonline.de/koscherliste/) weekly via GitHub Actions
- **Record classification** — each row is classified into one of three types:
  - `product` — a specific named product
  - `manufacturer_rule` — a standing brand-level rule, e.g. *"Alle Brotsorten"* (Kerry Ingredients) or *"Alle Teesorten"* (Meßmer)
  - `generic_rule` — an all-producer category rule, manufacturer = *"alle Firmen"*, e.g. *Butter*, *Honig*
- **Incremental updates** — existing products retain their permanent ID; only changed fields are updated
- **Stable product IDs** — MD5 hash of (raw_name, raw_manufacturer), assigned once on first encounter
- Detects dairy status (Milchig/Parve/Fleischig), Pessach certification, Chalaw Stam, encoding fixes
- Strips certificate and legal-suffix leakage from the manufacturer field
- Saves versioned snapshots to `scraper/snapshots/` (gitignored) when content changes
- Validation script (`validate_kosher_list.py`) checks for duplicates, near-duplicate names, weird characters

### Lookup logic (`KosherService.ts`)

Priority order — first matching tier wins:

| # | Tier | Condition | Match type |
|---|------|-----------|------------|
| 1 | **Trusted barcode** | Supabase has a confirmed `barcode → product_id` | `exact` |
| 2 | **Exact product** | Normalised name matches ORD product; brand overlaps if known | `exact` |
| 3 | **Fuzzy / manufacturer product** | Jaccard similarity ≥ 0.78 (same brand) or ≥ 0.56 (any brand) | `manufacturer` / `fuzzy` |
| 4 | **Manufacturer rule** | Brand overlaps rule manufacturer + keyword/category match | `manufacturer_rule` |
| 5 | **Generic rule** | Product name contains ORD category (e.g. "Butter", "Honig") | `generic_rule` |
| 6 | **No match** | | `none` |

Fuzzy matching uses token-set Jaccard similarity with bonuses for exact brand/name equality. No external fuzzy library is used — matching runs fully offline on the static JSON.

### Barcode confirmation (Supabase)

- On a fuzzy or manufacturer match, the user is asked *"Is this the correct product?"*
- **Confirm** → `barcode → product_id` stored in Supabase and shared with all users
- **Reject** → stored as a negative match
- On next scan of the same barcode → instant confirmed result from Supabase, no matching needed

---

## Data schema

### `kosher_list.json`

```json
{
  "version": "2026-03-16",
  "generated_at": "2026-03-16T06:12:33+00:00",
  "product_count": 1965,
  "products": [
    {
      "id": "a3f9c2b1d4e5",
      "source": "ORD",
      "record_type": "product",
      "scope": "product",
      "name": "Ritter Sport Vollmilch",
      "display_name": "Ritter Sport Vollmilch",
      "match_name": "ritter sport vollmilch",
      "manufacturer": "Ritter Sport",
      "certificate": "Rabbiner Yitschak Ehrenberg",
      "categories": ["Schokolade"],
      "dairy_status": "milchig",
      "dairy_note": "Chalaw Stam",
      "pessach": "unknown",
      "raw_name": "Ritter Sport Vollmilch",
      "raw_manufacturer": "Ritter Sport"
    },
    {
      "id": "b7d1e3f2a9c0",
      "source": "ORD",
      "record_type": "manufacturer_rule",
      "scope": "product",
      "rule_scope": "category",
      "applies_to_keywords": ["brot"],
      "name": "Alle Brotsorten",
      "display_name": "Alle Brotsorten",
      "match_name": "alle brotsorten",
      "manufacturer": "Kerry Ingredients",
      "categories": ["Brot"],
      "dairy_status": "unknown",
      "pessach": "unknown",
      "raw_name": "Alle Brotsorten",
      "raw_manufacturer": "Kerry Ingredients"
    }
  ],
  "manufacturer_index": {
    "ritter sport": ["a3f9c2b1d4e5"],
    "kerry ingredients": ["b7d1e3f2a9c0"]
  }
}
```

**`record_type` values:**

| Value | Meaning |
|-------|---------|
| `product` | Specific named product |
| `manufacturer_rule` | Standing rule for one manufacturer (e.g. *"Alle Teesorten"*) |
| `generic_rule` | All-producer category rule (manufacturer = *"alle Firmen"*) |

`scope` is preserved alongside `record_type` for backward compatibility with older app builds.

### `manifest.json`

```json
{
  "version": "2026-03-16",
  "generated_at": "2026-03-16T06:12:33+00:00",
  "product_count": 1965,
  "source": "https://koscherliste.ordonline.de/koscherliste/",
  "content_hash": "sha256:...",
  "scrape_stats": { "categories_found": 42, "categories_scraped": 40, ... },
  "diff_stats": { "added": 3, "removed": 0, "changed": 1 }
}
```

---

## Setup

### Scraper

```bash
pip install requests beautifulsoup4 pydantic rapidfuzz
python scraper/scraper.py
```

Output is saved to `scraper/output/`. GitHub Actions runs this automatically every Monday at 06:00 UTC.

To validate the output:

```bash
python scraper/validate_kosher_list.py
```

### App

```bash
cd KosherScanner
npm install
npx expo start --tunnel   # scan QR with Expo Go
```

---

## Costs

| Component | Cost |
|-----------|------|
| GitHub Actions scraper (weekly) | Free |
| GitHub raw file hosting | Free |
| Open Food Facts API | Free, no key |
| Supabase (barcode confirmation cache) | Free tier |
| Expo / React Native | Free |
| **Total** | **€0/month** |

---

## Roadmap

**Done**
- ORD scraper with incremental updates and stable product IDs
- Rule-aware data model: `product` / `manufacturer_rule` / `generic_rule`
- Six-tier matching with manufacturer rules and generic rules as explicit tiers
- Crowd-sourced barcode confirmation via Supabase
- Open Food Facts integration (barcode → product name + image)
- Animated result modal with distinct UI per match type
- Versioned snapshots and data-quality validation

**Planned**
- Private label / Eigenmarke manufacturer lookup (K-Classic → REWE, Ja! → REWE, etc.)
- Chalav Nochri flagging for dairy products
- Manual text search screen
- Category browser
- Pessach mode filter
- Multiple language support (DE / EN / HE)
- Israeli product sources (Badatz Eidah Hachareidis, Badatz Beit Yosef, Rabbanut Rashit)
- Additional European certification sources (KLBD, KO-Austria, Beth Din de Paris)
- Hebrew name normalisation (nikud stripping, spelling variants)
- User preference settings (Ashkenazi/Sephardi, Mehadrin, Chalav Yisrael only)
- Hechsher stamp recognition via camera (v2, requires ML model)

---

## Legal note

This app uses data from the ORD Koscherliste for informational purposes only. It is recommended to contact the ORD (info@ordonline.de) to inform them of the app and confirm they are comfortable with this use. The ORD list is the authoritative source — always verify with a rabbi if in doubt.

This project is independent and not affiliated with the ORD or any kosher certification authority.
