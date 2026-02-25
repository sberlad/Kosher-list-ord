/**
 * KosherService.ts
 *
 * Handles:
 *  1. Manifest version check on app launch
 *  2. Downloading & caching the kosher list JSON
 *  3. Product lookup by name / manufacturer
 *  4. Barcode → product name via Open Food Facts → kosher lookup
 */

import AsyncStorage from "@react-native-async-storage/async-storage";
import NetInfo from "@react-native-community/netinfo";

// ─── Config ──────────────────────────────────────────────────────────────────
// Point these at your GitHub raw URLs after you push the scraper output.
// e.g. https://raw.githubusercontent.com/YOUR-ORG/kosher-list-app/main/scraper/output/manifest.json
const MANIFEST_URL =
  "https://raw.githubusercontent.com/YOUR-ORG/kosher-list-app/main/scraper/output/manifest.json";
const LIST_URL =
  "https://raw.githubusercontent.com/YOUR-ORG/kosher-list-app/main/scraper/output/kosher_list.json";

const OPEN_FOOD_FACTS_URL = "https://world.openfoodfacts.org/api/v2/product";

// AsyncStorage keys
const KEY_LIST = "@kosher_list";
const KEY_VERSION = "@kosher_list_version";
const KEY_LAST_CHECK = "@kosher_last_check";

// Only re-check the manifest once per 24h to save bandwidth
const CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000;

// ─── Types ───────────────────────────────────────────────────────────────────
export type DairyStatus = "milchig" | "parve" | "fleischig" | "unknown";
export type PessachStatus =
  | "kosher_lepessach"
  | "suitable"
  | "not_pessach"
  | "unknown";

export interface KosherProduct {
  name: string;
  manufacturer: string;
  certificate: string;
  dairy_status: DairyStatus;
  pessach: PessachStatus;
  categories: string[];
}

export interface KosherList {
  version: string;
  generated_at: string;
  product_count: number;
  products: KosherProduct[];
  manufacturer_index: Record<string, string[]>;
}

export interface LookupResult {
  found: boolean;
  product?: KosherProduct;
  /** Set when the product itself isn't listed but its manufacturer is */
  manufacturer_match?: {
    manufacturer: string;
    note: string;
  };
  barcode_product_name?: string;
  barcode_manufacturer?: string;
}

// ─── KosherService ───────────────────────────────────────────────────────────
class KosherService {
  private list: KosherList | null = null;

  /** Call once on app startup */
  async initialise(): Promise<{ updated: boolean; version: string | null }> {
    // Load cached list into memory immediately so the app is usable offline
    await this.loadFromCache();

    const net = await NetInfo.fetch();
    if (!net.isConnected) {
      console.log("[KosherService] Offline — using cached list");
      return { updated: false, version: this.list?.version ?? null };
    }

    // Rate-limit manifest checks to once per CHECK_INTERVAL_MS
    const lastCheck = await AsyncStorage.getItem(KEY_LAST_CHECK);
    const now = Date.now();
    if (lastCheck && now - parseInt(lastCheck, 10) < CHECK_INTERVAL_MS) {
      console.log("[KosherService] Manifest check skipped (checked recently)");
      return { updated: false, version: this.list?.version ?? null };
    }

    return this.checkForUpdates();
  }

  /** Compare manifest version with cached version and download if newer */
  async checkForUpdates(): Promise<{
    updated: boolean;
    version: string | null;
  }> {
    try {
      const manifestResp = await fetch(MANIFEST_URL, { cache: "no-store" });
      if (!manifestResp.ok) throw new Error("Manifest fetch failed");
      const manifest = await manifestResp.json();

      await AsyncStorage.setItem(KEY_LAST_CHECK, Date.now().toString());

      const cachedVersion = await AsyncStorage.getItem(KEY_VERSION);

      if (cachedVersion === manifest.version) {
        console.log(`[KosherService] List is current (${manifest.version})`);
        return { updated: false, version: manifest.version };
      }

      console.log(
        `[KosherService] New version ${manifest.version} — downloading…`
      );
      await this.downloadAndCache();
      return { updated: true, version: this.list?.version ?? null };
    } catch (e) {
      console.warn("[KosherService] Update check failed:", e);
      return { updated: false, version: this.list?.version ?? null };
    }
  }

  private async downloadAndCache(): Promise<void> {
    const resp = await fetch(LIST_URL, { cache: "no-store" });
    if (!resp.ok) throw new Error("List download failed");
    const text = await resp.text();
    const data: KosherList = JSON.parse(text);

    await AsyncStorage.setItem(KEY_LIST, text);
    await AsyncStorage.setItem(KEY_VERSION, data.version);
    this.list = data;
    console.log(
      `[KosherService] Downloaded ${data.product_count} products (v${data.version})`
    );
  }

  private async loadFromCache(): Promise<void> {
    try {
      const cached = await AsyncStorage.getItem(KEY_LIST);
      if (cached) {
        this.list = JSON.parse(cached);
        console.log(
          `[KosherService] Loaded ${this.list?.product_count} products from cache`
        );
      }
    } catch (e) {
      console.warn("[KosherService] Cache load failed:", e);
    }
  }

  // ─── Lookup ──────────────────────────────────────────────────────────────

  /**
   * Full barcode lookup flow:
   *   barcode → Open Food Facts → product name + manufacturer → kosher check
   */
  async lookupBarcode(barcode: string): Promise<LookupResult> {
    if (!this.list) {
      return { found: false };
    }

    let productName: string | undefined;
    let manufacturer: string | undefined;

    // 1. Query Open Food Facts
    try {
      const resp = await fetch(
        `${OPEN_FOOD_FACTS_URL}/${barcode}?fields=product_name,brands,manufacturer`,
        { cache: "default" }
      );
      if (resp.ok) {
        const data = await resp.json();
        if (data.status === 1 && data.product) {
          productName = data.product.product_name;
          manufacturer = data.product.brands ?? data.product.manufacturer;
        }
      }
    } catch (e) {
      console.warn("[KosherService] Open Food Facts error:", e);
    }

    // 2. Search kosher list
    return this.lookupByNameAndManufacturer(productName, manufacturer);
  }

  /**
   * Direct text search — useful for manual search screen.
   */
  lookupByText(query: string): KosherProduct[] {
    if (!this.list) return [];
    const q = query.toLowerCase().trim();
    return this.list.products.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.manufacturer.toLowerCase().includes(q)
    );
  }

  /**
   * Core matching logic.
   * Priority:
   *   1. Exact product name match
   *   2. Fuzzy product name match (contains)
   *   3. Manufacturer match (own-brand scenario)
   */
  lookupByNameAndManufacturer(
    productName?: string,
    manufacturer?: string
  ): LookupResult {
    if (!this.list) return { found: false };

    const nameLower = productName?.toLowerCase().trim() ?? "";
    const mfrLower = manufacturer?.toLowerCase().trim() ?? "";

    // 1. Exact product name
    const exact = this.list.products.find(
      (p) => p.name.toLowerCase() === nameLower
    );
    if (exact) {
      return {
        found: true,
        product: exact,
        barcode_product_name: productName,
        barcode_manufacturer: manufacturer,
      };
    }

    // 2. Fuzzy product name (contains in either direction)
    if (nameLower.length > 2) {
      const fuzzy = this.list.products.find(
        (p) =>
          p.name.toLowerCase().includes(nameLower) ||
          nameLower.includes(p.name.toLowerCase())
      );
      if (fuzzy) {
        return {
          found: true,
          product: fuzzy,
          barcode_product_name: productName,
          barcode_manufacturer: manufacturer,
        };
      }
    }

    // 3. Manufacturer match (own-brand scenario)
    if (mfrLower.length > 1) {
      // Check manufacturer index first (normalised names)
      const indexMatch = Object.keys(this.list.manufacturer_index).find(
        (m) => m.includes(mfrLower) || mfrLower.includes(m)
      );
      if (indexMatch) {
        return {
          found: false,
          manufacturer_match: {
            manufacturer: indexMatch,
            note: `This product's manufacturer (${manufacturer}) is certified kosher by ORD. The specific product may or may not be covered — check the label for a hechsher.`,
          },
          barcode_product_name: productName,
          barcode_manufacturer: manufacturer,
        };
      }
    }

    return {
      found: false,
      barcode_product_name: productName,
      barcode_manufacturer: manufacturer,
    };
  }

  get isLoaded(): boolean {
    return this.list !== null;
  }

  get listVersion(): string | null {
    return this.list?.version ?? null;
  }

  get productCount(): number {
    return this.list?.product_count ?? 0;
  }
}

export const kosherService = new KosherService();
