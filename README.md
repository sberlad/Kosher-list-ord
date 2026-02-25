# Kosher Scanner App


An iOS & Android app that scans product barcodes and checks them against the
[ORD (Orthodoxe Rabbinerkonferenz Deutschland) Koscherliste](https://koscherliste.ordonline.de/).

---

## How it works

```
Barcode scan
    │
    ▼
Open Food Facts API      ← free, no key needed
(barcode → product name + manufacturer)
    │
    ▼
Local kosher_list.json   ← cached on device, auto-updated weekly
(name + manufacturer lookup)
    │
    ├─ Direct match   → ✅ Kosher (ORD certified)
    ├─ Mfr. match     → ⚠️  Manufacturer is certified (check label)
    └─ No match       → ❌ Not on ORD list
```

The app never needs a backend server. All data is served as static JSON
from GitHub (or any CDN).

---

## Repository structure

```
kosher-list-app/
├── scraper/
│   ├── scraper.py          # Python scraper — pulls ORD list
│   └── output/
│       ├── kosher_list.json   # Full product database
│       └── manifest.json      # Version info for app update check
│
├── .github/
│   └── workflows/
│       └── scrape.yml      # GitHub Actions — runs scraper every Monday
│
└── app/                    # React Native app
    ├── services/
    │   └── KosherService.ts   # Core logic: version check, download, lookup
    ├── screens/
    │   └── ScannerScreen.tsx  # Camera + barcode scan UI
    └── components/
        └── ResultModal.tsx    # Result display (green/amber/red)
```

---

## Setup

### 1. Scraper (one-time + automated)

```bash
pip install requests beautifulsoup4
python scraper/scraper.py
```

Output files are saved to `scraper/output/`. Commit them to your repo.

GitHub Actions runs the scraper every Monday at 06:00 UTC automatically.
If the list hasn't changed, nothing is committed (no noise).

### 2. Configure the app

In `app/services/KosherService.ts`, update the two URLs to point at your
GitHub raw file URLs:

```ts
const MANIFEST_URL =
  "https://raw.githubusercontent.com/YOUR-ORG/kosher-list-app/main/scraper/output/manifest.json";
const LIST_URL =
  "https://raw.githubusercontent.com/YOUR-ORG/kosher-list-app/main/scraper/output/kosher_list.json";
```

### 3. React Native app

```bash
npx react-native init KosherApp --template react-native-template-typescript
cd KosherApp

# Install dependencies
npm install \
  react-native-vision-camera \
  vision-camera-code-scanner \
  @react-native-community/netinfo \
  @react-native-async-storage/async-storage \
  react-native-reanimated

# iOS
cd ios && pod install && cd ..
npx react-native run-ios

# Android
npx react-native run-android
```

Add camera permission to `AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.CAMERA" />
```

Add to `Info.plist` (iOS):
```xml
<key>NSCameraUsageDescription</key>
<string>Used to scan product barcodes</string>
```

---

## On-launch update flow

```
App opens
    │
    ├─ Load cached kosher_list.json from AsyncStorage (instant, works offline)
    │
    └─ Internet available?
           │
           ├─ Yes → Last checked > 24h ago?
           │              │
           │              ├─ Yes → Fetch manifest.json (tiny, ~200 bytes)
           │              │           Same version? → Do nothing
           │              │           New version?  → Download full list
           │              │
           │              └─ No  → Skip (checked recently)
           │
           └─ No  → Use cache, show "Last updated X days ago"
```

---

## Data structure

### manifest.json
```json
{
  "version": "2025-02-24",
  "generated_at": "2025-02-24T06:12:33+00:00",
  "product_count": 1842,
  "source": "https://koscherliste.ordonline.de/koscherliste/"
}
```

### kosher_list.json (excerpt)
```json
{
  "version": "2025-02-24",
  "product_count": 1842,
  "products": [
    {
      "name": "Ritter Sport Schokolade",
      "manufacturer": "Ritter Sport",
      "certificate": "Rabbiner Yitschak Ehrenberg",
      "dairy_status": "milchig",
      "pessach": "unknown",
      "categories": ["Schokolade", "Süßwaren"]
    }
  ],
  "manufacturer_index": {
    "ritter sport": ["Ritter Sport Schokolade", "..."],
    "dr. oetker": ["..."]
  }
}
```

---

## Lookup priority

1. **Exact name match** — product name from Open Food Facts exactly matches ORD listing → ✅
2. **Fuzzy name match** — one contains the other → ✅
3. **Manufacturer match** — manufacturer is certified but specific product not listed → ⚠️ (check for hechsher on packaging)
4. **No match** → ❌

---

## Costs

| Component | Cost |
|-----------|------|
| GitHub Actions scraper (weekly) | Free |
| GitHub raw file hosting | Free |
| Open Food Facts API | Free, no key |
| React Native | Free / open source |
| **Total** | **€0/month** |

---

## Future features

- [ ] Manual text search screen
- [ ] Category browser
- [ ] Own-brand / Eigenmarke manufacturer mapping database
- [ ] Pessach mode filter
- [ ] Multiple language support (DE/EN/FR/HE)
- [ ] Community-reported product corrections

---

## Legal note

This app uses data from the ORD Koscherliste for informational purposes.
It is recommended to contact the ORD (info@ordonline.de) to inform them
of the app and confirm they are comfortable with this use.
The ORD list is the authoritative source — always verify with a rabbi
if in doubt.
