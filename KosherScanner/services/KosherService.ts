type DairyStatus = "milchig" | "parve" | "fleischig" | "unknown";
type PessachStatus = "kosher_lepessach" | "not_pessach" | "unknown";
type ProductScope = "product" | "generic_rule";
type RecordType = "product" | "manufacturer_rule" | "generic_rule";
type RuleScope = "category" | "all_products";
type MatchType = "exact" | "fuzzy" | "manufacturer" | "manufacturer_rule" | "generic_rule" | "none";
type ResultStatus = "kosher" | "not_kosher" | "unknown";

const KOSHER_LIST_URL =
  "https://raw.githubusercontent.com/sberlad/Kosher-list-ord/main/scraper/output/kosher_list.json";

export interface KosherProduct {
  id: string;
  source: "ORD";
  /** Canonical classification. Added in schema v2; fall back to `scope` for old data. */
  record_type?: RecordType;
  /** Kept for backward compatibility. Use `record_type` when possible. */
  scope: ProductScope;
  /** For rule entries: whether the rule covers a category or all products. */
  rule_scope?: RuleScope;
  /** Keywords extracted from the rule name (e.g. ["brot"] for "Alle Brotsorten"). */
  applies_to_keywords?: string[];
  name: string;
  display_name?: string;
  match_name: string;
  manufacturer: string;
  certificate?: string;
  categories: string[];
  dairy_status: DairyStatus;
  pessach: PessachStatus;
  size?: string;
  raw_name: string;
  raw_manufacturer: string;
  dairy_note?: string;
  pessach_note?: string;
  variants?: string[];
}

export interface KosherData {
  version: string;
  generated_at?: string;
  product_count: number;
  products: KosherProduct[];
  manufacturer_index?: Record<string, string[]>;
}

export interface LookupInput {
  barcode?: string;
  name: string;
  brand?: string;
}

export interface MatchedProductSummary {
  id: string;
  name: string;
  manufacturer: string;
  size?: string;
  categories?: string[];
}

export interface OffProductInfo {
  name: string;
  brand?: string;
  imageUrl?: string;
}

export interface LookupResult {
  status: ResultStatus;
  matchType: MatchType;
  confidence: number;
  source: "ORD";
  certificate?: string;
  reason?: string;
  needsConfirmation?: boolean;
  matchedProduct?: MatchedProductSummary;
  manufacturerProducts?: MatchedProductSummary[];
  /** Open Food Facts product data used as input for the ORD match. */
  offProduct?: OffProductInfo;
}

let cachedData: KosherData | null = null;
let lastFetched = 0;
const CACHE_TTL = 24 * 60 * 60 * 1000;

export async function loadKosherData(forceRefresh = false): Promise<KosherData> {
  const now = Date.now();

  if (!forceRefresh && cachedData && now - lastFetched < CACHE_TTL) {
    return cachedData;
  }

  const response = await fetch(KOSHER_LIST_URL);

  if (!response.ok) {
    throw new Error(`Failed to load kosher data: ${response.status} ${response.statusText}`);
  }

  const data = (await response.json()) as KosherData;

  if (!data?.products || !Array.isArray(data.products)) {
    throw new Error("Invalid kosher data format");
  }

  cachedData = data;
  lastFetched = now;
  return data;
}

function normalize(text?: string): string {
  return (text ?? "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ß/g, "ss")
    .replace(/&/g, " and ")
    .replace(/['’`]/g, "")
    .replace(/\b(zero sugar|zero zucker)\b/g, "zero")
    .replace(/\b(co\.?|company|gmbh|llc|kg|ag|ltd)\b/g, " ")
    .replace(/\b\d+(?:[.,]\d+)?\s*(ml|l|g|kg|cl)\b/gi, " ")
    .replace(/\b(x\s?\d+|multipack|trinkpack|glass|bio)\b/gi, " ")
    .replace(/[^a-z0-9äöü\s/+.-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeBrand(text?: string): string {
  return normalize(text)
    .replace(/\bcoca cola\b/g, "coca cola")
    .replace(/\bthe coca cola company\b/g, "coca cola")
    .replace(/\bben and jerry\b/g, "ben jerry")
    .trim();
}

function tokens(text?: string): string[] {
  return normalize(text)
    .split(" ")
    .map((t) => t.trim())
    .filter(Boolean);
}

function tokenSet(text?: string): Set<string> {
  return new Set(tokens(text));
}

function jaccardScore(a?: string, b?: string): number {
  const aa = tokenSet(a);
  const bb = tokenSet(b);

  if (!aa.size || !bb.size) return 0;

  let intersection = 0;
  for (const token of aa) {
    if (bb.has(token)) intersection += 1;
  }

  const union = aa.size + bb.size - intersection;
  return union > 0 ? intersection / union : 0;
}

function exactishEqual(a?: string, b?: string): boolean {
  return normalize(a) === normalize(b);
}

function brandOverlap(a?: string, b?: string): boolean {
  const aa = tokenSet(normalizeBrand(a));
  const bb = tokenSet(normalizeBrand(b));

  if (!aa.size || !bb.size) return false;

  let overlap = 0;
  for (const token of aa) {
    if (bb.has(token)) overlap += 1;
  }

  return overlap > 0;
}

/** Resolve record_type for entries that may predate the schema v2 field. */
function getRecordType(p: KosherProduct): RecordType {
  if (p.record_type) return p.record_type;
  return p.scope === "generic_rule" ? "generic_rule" : "product";
}

/**
 * Score how well a manufacturer rule covers the scanned product.
 * Returns 0 if the rule does not apply.
 *
 * Matching logic:
 *  1. Brand must overlap with the rule's manufacturer.
 *  2. If rule_scope == "all_products" or no keywords: any product qualifies.
 *  3. Otherwise: the product name must contain at least one applies_to_keyword
 *     OR overlap with the rule's ORD categories.
 */
function matchManufacturerRule(
  inputName: string,
  inputBrand: string,
  rule: KosherProduct
): number {
  if (!inputBrand || !brandOverlap(inputBrand, rule.manufacturer)) return 0;

  const keywords = rule.applies_to_keywords ?? [];

  if (rule.rule_scope === "all_products" || keywords.length === 0) {
    return 0.85;
  }

  const inputNorm = normalize(inputName);

  if (keywords.some((kw) => inputNorm.includes(normalize(kw)))) {
    return 0.85;
  }

  const catMatch = (rule.categories ?? []).some((cat) => {
    const catNorm = normalize(cat);
    return catNorm.length >= 3 && inputNorm.includes(catNorm);
  });
  if (catMatch) return 0.75;

  return 0;
}

function summarizeProduct(product: KosherProduct): MatchedProductSummary {
  return {
    id: product.id,
    name: product.display_name || product.name,
    manufacturer: product.manufacturer,
    size: product.size,
    categories: product.categories,
  };
}

function uniqueManufacturerProducts(products: KosherProduct[], limit = 8): MatchedProductSummary[] {
  const seen = new Set<string>();
  const out: MatchedProductSummary[] = [];

  for (const product of products) {
    if (seen.has(product.id)) continue;
    seen.add(product.id);
    out.push(summarizeProduct(product));
    if (out.length >= limit) break;
  }

  return out;
}

function createNoneResult(reason = "No ORD match found."): LookupResult {
  return {
    status: "unknown",
    matchType: "none",
    confidence: 0,
    source: "ORD",
    reason,
  };
}

function scoreCandidate(inputName: string, inputBrand: string, product: KosherProduct): number {
  const productName = product.match_name || product.name;
  const nameScore = jaccardScore(inputName, productName);
  const manufacturerScore = inputBrand ? jaccardScore(inputBrand, product.manufacturer) : 0;

  let score = nameScore * 0.8 + manufacturerScore * 0.2;

  if (exactishEqual(inputName, productName)) {
    score += 0.25;
  }

  if (inputBrand && exactishEqual(inputBrand, product.manufacturer)) {
    score += 0.2;
  }

  if (inputBrand && brandOverlap(inputBrand, product.manufacturer)) {
    score += 0.1;
  }

  return Math.min(score, 1);
}

function genericRuleScore(inputName: string, product: KosherProduct): number {
  const genericName = normalize(product.name);
  if (!genericName) return 0;

  if (inputName === genericName) return 0.9;
  if (inputName.includes(genericName)) return 0.72;
  if (genericName.includes(inputName) && inputName.length >= 5) return 0.62;

  return jaccardScore(inputName, genericName) * 0.75;
}

export async function lookupProduct(input: LookupInput): Promise<LookupResult> {
  const data = await loadKosherData();
  const products = data.products ?? [];

  const inputName = normalize(input.name);
  const inputBrand = normalizeBrand(input.brand);

  if (!inputName) {
    return createNoneResult("No product name available for lookup.");
  }

  const productRecords = products.filter((p) => getRecordType(p) === "product");
  const manufacturerRules = products.filter((p) => getRecordType(p) === "manufacturer_rule");
  const genericRules = products.filter((p) => getRecordType(p) === "generic_rule");

  // 1. Exact product match: exact normalized name + optional exact/overlapping brand
  const exactMatch = productRecords.find((p) => {
    const exactName = exactishEqual(p.match_name || p.name, inputName);
    if (!exactName) return false;

    if (!inputBrand) return true;
    return exactishEqual(p.manufacturer, inputBrand) || brandOverlap(p.manufacturer, inputBrand);
  });

  if (exactMatch) {
    return {
      status: "kosher",
      matchType: "exact",
      confidence: 1,
      source: "ORD",
      certificate: exactMatch.certificate,
      matchedProduct: summarizeProduct(exactMatch),
    };
  }

  // 2. Strong manufacturer match with close name score
  const sameBrandCandidates = inputBrand
    ? productRecords
        .filter(
          (p) =>
            exactishEqual(p.manufacturer, inputBrand) ||
            brandOverlap(p.manufacturer, inputBrand)
        )
        .map((p) => ({
          product: p,
          score: scoreCandidate(input.name, input.brand ?? "", p),
        }))
        .sort((a, b) => b.score - a.score)
    : [];

  if (sameBrandCandidates.length > 0 && sameBrandCandidates[0].score >= 0.78) {
    const best = sameBrandCandidates[0].product;
    const bestScore = sameBrandCandidates[0].score;

    return {
      status: "kosher",
      matchType: bestScore >= 0.9 ? "exact" : "manufacturer",
      confidence: bestScore,
      source: "ORD",
      certificate: best.certificate,
      matchedProduct: summarizeProduct(best),
      manufacturerProducts: uniqueManufacturerProducts(
        sameBrandCandidates.map((x) => x.product)
      ),
      needsConfirmation: bestScore < 0.9,
      reason: bestScore < 0.9 ? "Matched by manufacturer and similar product name." : undefined,
    };
  }

  // 3. Best fuzzy product candidate
  const fuzzyCandidates = productRecords
    .map((p) => ({
      product: p,
      score: scoreCandidate(input.name, input.brand ?? "", p),
    }))
    .filter((x) => x.score >= 0.56)
    .sort((a, b) => b.score - a.score);

  if (fuzzyCandidates.length > 0) {
    const best = fuzzyCandidates[0].product;
    const bestScore = fuzzyCandidates[0].score;

    return {
      status: "kosher",
      matchType: bestScore >= 0.75 ? "fuzzy" : "manufacturer",
      confidence: bestScore,
      source: "ORD",
      certificate: best.certificate,
      matchedProduct: summarizeProduct(best),
      needsConfirmation: true,
      reason: "Possible ORD match — verify product details.",
    };
  }

  // 4. Manufacturer rule — a standing ORD rule for this brand
  //    (e.g. "Alle Brotsorten" from Kerry Ingredients).
  //    Only checked when a brand is known and product matching failed.
  if (inputBrand && manufacturerRules.length > 0) {
    const ruleCandidates = manufacturerRules
      .map((r) => ({ rule: r, score: matchManufacturerRule(input.name, input.brand ?? "", r) }))
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score);

    if (ruleCandidates.length > 0) {
      const best = ruleCandidates[0].rule;
      const bestScore = ruleCandidates[0].score;

      return {
        status: "kosher",
        matchType: "manufacturer_rule",
        confidence: bestScore,
        source: "ORD",
        certificate: best.certificate,
        matchedProduct: summarizeProduct(best),
        needsConfirmation: true,
        reason: best.name,
      };
    }
  }

  // 5. Generic rule fallback (alle Firmen etc.)
  const genericCandidates = genericRules
    .map((p) => ({
      product: p,
      score: genericRuleScore(inputName, p),
    }))
    .filter((x) => x.score >= 0.6)
    .sort((a, b) => b.score - a.score);

  if (genericCandidates.length > 0) {
    const best = genericCandidates[0].product;
    const bestScore = genericCandidates[0].score;

    return {
      status: "kosher",
      matchType: "generic_rule",
      confidence: bestScore,
      source: "ORD",
      certificate: best.certificate,
      matchedProduct: summarizeProduct(best),
      reason: "Matched via generic ORD rule.",
    };
  }

  // Debug: log top candidates that almost matched so misses can be diagnosed
  const topCandidates = productRecords
    .map((p) => ({ id: p.id, name: p.name, score: scoreCandidate(input.name, input.brand ?? "", p) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);
  console.debug(
    `[KosherService] No ORD match for "${input.name}" / "${input.brand ?? ""}". Top candidates:`,
    topCandidates.map((c) => `${c.name} (${c.score.toFixed(3)})`).join(", ")
  );

  return createNoneResult();
}

export function getProductById(
  products: KosherProduct[],
  productId: string
): KosherProduct | null {
  for (const product of products) {
    if (product.id === productId) {
      return product;
    }
  }
  return null;
}