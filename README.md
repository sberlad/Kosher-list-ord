Here’s the full updated README — paste this into the file:

# Kosher Scanner App

> **Project goal:** To explore AI-assisted software development workflows while building a practical tool for kosher consumers in Germany.

An iOS & Android app that scans product barcodes and checks them against the ORD (Orthodoxe Rabbinerkonferenz Deutschland) Koscherliste.

## How it works



Barcode scan
│
▼
Open Food Facts API      ← free, no key needed
(barcode → product name + manufacturer)
│
▼
Barcode Cache (Supabase) ← checked first for confirmed matches
│
▼
Local kosher_list.json   ← cached on device, auto-updated weekly
(name + manufacturer lookup)
│
├─ Direct match      → ✅ Kosher (ORD certified)
├─ Fuzzy match       → ⚠️  Possible match (user confirmation requested)
├─ Mfr. match        → 🏭 Manufacturer is certified (check label)
├─ Inherently kosher → 💧 Kosher without supervision (water, plain produce etc.)
└─ No match          → ❌ Not on ORD list


The app never needs a backend server for lookups. All kosher list data is served as static JSON from GitHub. Confirmed barcode matches are stored in Supabase (free tier).

---

## Repository structure



Kosher-list-ord/
├── scraper/
│   ├── scraper.py             # Python scraper — pulls ORD Koscherliste
│   └── output/
│       ├── kosher_list.json   # Full product database (stable IDs, incremental updates)
│       └── manifest.json      # Version info for app update check
│
├── .github/
│   └── workflows/
│       └── scrape.yml         # GitHub Actions — runs scraper every Monday
│
└── KosherScanner/             # React Native (Expo) app
├── app/
│   ├── _layout.tsx
│   └── index.tsx          # Camera + barcode scan UI
├── services/
│   ├── KosherService.ts   # Core logic: lookup, fuzzy matching, caching
│   └── OpenFoodFacts.ts   # OFF API integration
└── components/
└── ResultModal.tsx    # in Result display


---

## Data pipeline

### Scraper
- Scrapes [ORD Koscherliste](https://koscherliste.ordonline.de/koscherliste/) weekly via GitHub Actions
- **Incremental updates** — existing products retain their permanent ID; only changed fields are updated
- **Stable product IDs** — assigned once on first encounter (hash of name + manufacturer), never regenerated
- Detects dairy status (Milchig/Parve), Pessach certification, Chalaw Stam, Kitniot notes
- Cleans encoding issues (· → ß), strips certificate/brand leakage from manufacturer field

### Lookup logic (priority order)
1. **Barcode cache** (Supabase) — confirmed exact match from previous scan
2. **Exact name match** — normalized product name matches ORD listing exactly
3. **Contains match** — one name contains the other (with brand verification)
4. **Manufacturer match** — brand certified, specific product not listed
5. **Fuzzy name match** — Fuse.js similarity above threshold (user confirmation requested)
6. **Inherently kosher rules engine** — product category/ingredients indicate kosher without supervision
7. **No match**

### Barcode cache (Supabase)
- User confirms a fuzzy/manufacturer match → `barcode → product_id` stored permanently
- On next scan of same barcode → instant confirmed result, no matching needed
- Shared across all users — crowd-sourced improvement over time

---

## Data structure

### manifest.json
```json
{
  "version": "2026-03-09",
  "generated_at": "2026-03-09T06:12:33+00:00",
  "product_count": 1932,
  "source": "https://koscherliste.ordonline.de/koscherliste/"
}


kosher_list.json (excerpt)

{
  "version": "2026-03-09",
  "product_count": 1932,
  "products": [
    {
      "id": "a3f9c2b1d4e5",
      "name": "Ritter Sport Schokolade",
      "manufacturer": "Ritter Sport",
      "certificate": "Rabbiner Yitschak Ehrenberg",
      "dairy_status": "milchig",
      "dairy_note": "Chalaw Stam",
      "pessach": "unknown",
      "pessach_note": "",
      "categories": ["Schokolade", "Süßwaren"],
      "weitere_kategorien": ""
    }
  ]
}


Setup
1. Scraper

pip install requests beautifulsoup4
python scraper/scraper.py


Output saved to scraper/output/. GitHub Actions runs this every Monday at 06:00 UTC automatically.
2. App

cd KosherScanner
npm install
npx expo start --tunnel


Costs



|Component                      |Cost        |
|-------------------------------|------------|
|GitHub Actions scraper (weekly)|Free        |
|GitHub raw file hosting        |Free        |
|Open Food Facts API            |Free, no key|
|Supabase (barcode cache)       |Free tier   |
|Expo / React Native            |Free        |
|**Total**                      |**€0/month**|

Roadmap
In progress
	∙	Supabase barcode cache integration
	∙	Scraper incremental updates + stable product IDs
Planned
	∙	Inherently kosher rules engine (water, plain produce, unsupervised staples)
	∙	Chalav Nochri flagging for dairy products
	∙	Private label / Eigenmarke manufacturer lookup
	∙	Mapping house brands (K-Classic, Ja!, Gut & Günstig etc.) to real manufacturers
	∙	Check if underlying manufacturer is certified → “Probably Kosher”
	∙	Investigating MarkenDetektive data and Open Food Facts brand fields
	∙	Israeli product sources
	∙	Rabbanut Rashit (Chief Rabbinate) database
	∙	Badatz Eidah Hachareidis, Badatz Beit Yosef, Badatz Mehadrin
	∙	Hebrew name normalization (nikud stripping, spelling variants)
	∙	Additional European certification sources
	∙	KLBD (UK), KO-Austria, Beth Din de Paris
	∙	User preference settings (Ashkenazi/Sephardi, Mehadrin, Chalav Yisrael only)
	∙	Manual text search screen
	∙	Category browser
	∙	Pessach mode filter
	∙	Multiple language support (DE/EN/HE/FR)
	∙	Hechsher stamp recognition via camera (v2, requires ML)

Legal note
This app uses data from the ORD Koscherliste for informational purposes. It is recommended to contact the ORD (info@ordonline.de) to inform them of the app and confirm they are comfortable with this use. The ORD list is the authoritative source — always verify with a rabbi if in doubt.
This project is independent and not affiliated with the ORD or any kosher certification authority.
