/**
 * AdvisoryService — "no hechsher needed" guidance layer.
 *
 * This is ENTIRELY SEPARATE from ORD certification data.
 * Records here come from external policy sources (STAR-K, cRc) and represent
 * general guidance that certain simple, unprocessed items do not require a
 * kosher symbol — they are NOT product-specific certifications.
 *
 * Sources:
 *   STAR-K "Approved Without A Hechsher" list
 *   cRc  "No Hechsher Needed" list
 *
 * UI contract:
 *   - Only shown when ORD returns matchType === "none"
 *   - Displayed as advisory guidance, not as kosher certification
 *   - Source name (STAR-K / cRc) always surfaced to the user
 *   - Conditions and caveats always shown when present
 */

export type AdvisorySource = "STAR-K" | "cRc";

export interface AdvisoryRule {
  id: string;
  source: AdvisorySource;
  record_type: "advisory_rule";
  rule_scope: "product_type";
  /** Keywords used to match against scanned product name (normalized). */
  applies_to_keywords: string[];
  /** OFF category strings that can trigger a match when the name alone doesn't match. */
  categories: string[];
  /** Plain-language explanation shown to the user. */
  note: string;
  /** Conditions / limitations under which the advisory applies. */
  conditions?: string;
  /** Passover applicability. "kitniyot" = Ashkenazi restriction applies. */
  passover?: "yes" | "no" | "unknown" | "kitniyot";
  /** Country-of-origin caveat, if any. */
  country_of_origin_caveat?: string;
  /** How conservatively this advisory should be trusted. */
  advisory_confidence: "high" | "medium";
  /** Short provenance note shown to user alongside source name. */
  source_note?: string;
}

export interface AdvisoryMatch {
  source: AdvisorySource;
  confidence: number;
  matchedRule: AdvisoryRule;
}

// ---------------------------------------------------------------------------
// Starter dataset — manually seeded, conservative.
// Only plain, unprocessed single-ingredient items with broad halachic consensus.
// ---------------------------------------------------------------------------
const ADVISORY_RULES: AdvisoryRule[] = [
  {
    id: "adv-flour-001",
    source: "STAR-K",
    record_type: "advisory_rule",
    rule_scope: "product_type",
    applies_to_keywords: [
      "mehl", "flour", "wheat flour", "weizenmehl", "weissmehl",
      "weizen mehl", "plain flour", "all purpose flour", "allzweckmehl",
    ],
    categories: ["flour", "baking ingredients", "wheat flour", "mehl"],
    note: "Plain white or wheat flour generally does not require a hechsher.",
    conditions:
      "Plain unflavored flour only. Enriched, self-raising, bread, or blended flours may require certification. Check for additives.",
    passover: "no",
    country_of_origin_caveat:
      "Some authorities require certification for flour from certain regions. When in doubt, consult your rabbi.",
    advisory_confidence: "high",
    source_note:
      "STAR-K: Plain flour (without additives) appears on the 'approved without a hechsher' list.",
  },
  {
    id: "adv-sugar-001",
    source: "STAR-K",
    record_type: "advisory_rule",
    rule_scope: "product_type",
    applies_to_keywords: [
      "zucker", "sugar", "white sugar", "granulated sugar", "weisszucker",
      "kristallzucker", "feinzucker", "haushaltzucker",
    ],
    categories: ["sugar", "sweeteners", "granulated sugar", "white sugar"],
    note: "Plain white granulated sugar generally does not require a hechsher.",
    conditions:
      "Plain white sugar only. Powdered/icing sugar, brown sugar, raw sugar, flavored sugars, and sugar products require certification.",
    passover: "yes",
    advisory_confidence: "high",
    source_note:
      "STAR-K / cRc: Plain white granulated sugar is on the 'no hechsher needed' list.",
  },
  {
    id: "adv-tea-001",
    source: "cRc",
    record_type: "advisory_rule",
    rule_scope: "product_type",
    applies_to_keywords: [
      "tee", "tea", "green tea", "black tea", "white tea",
      "gruner tee", "schwarzer tee", "weisser tee",
    ],
    categories: ["tea", "herbal tea", "green tea", "black tea", "beverages"],
    note: "Plain unflavored tea (black, green, white) generally does not require a hechsher.",
    conditions:
      "Plain tea bags or loose-leaf tea only. Flavored teas, decaffeinated teas, tea blends with additives, and instant tea require certification.",
    passover: "unknown",
    advisory_confidence: "medium",
    source_note:
      "cRc: Plain unflavored tea is generally acceptable without kosher certification.",
  },
  {
    id: "adv-salt-001",
    source: "STAR-K",
    record_type: "advisory_rule",
    rule_scope: "product_type",
    applies_to_keywords: [
      "salz", "salt", "table salt", "sea salt", "meeressalz",
      "tafelsalz", "kochsalz", "speisesalz", "kosher salt",
    ],
    categories: ["salt", "seasoning", "spices", "salz"],
    note: "Plain salt (table salt, sea salt, kosher salt) does not require a hechsher.",
    conditions:
      "Plain salt only. Flavored salts, seasoning salts, iodized blends, or salts with added ingredients require certification.",
    passover: "yes",
    advisory_confidence: "high",
    source_note: "STAR-K: Plain salt requires no hechsher.",
  },
  {
    id: "adv-rice-001",
    source: "cRc",
    record_type: "advisory_rule",
    rule_scope: "product_type",
    applies_to_keywords: [
      "reis", "rice", "white rice", "weisser reis", "long grain rice",
      "basmati", "jasmine rice", "jasminreis", "basmati reis",
    ],
    categories: ["rice", "grains", "staple foods", "white rice"],
    note: "Plain white rice generally does not require a hechsher.",
    conditions:
      "Plain uncooked rice only. Instant rice, parboiled rice, flavored rice, rice mixes, and rice cakes require certification.",
    passover: "kitniyot",
    advisory_confidence: "medium",
    source_note:
      "cRc: Plain uncooked white rice is acceptable without certification. Note: kitniyot for Pesach (Ashkenazi).",
  },
];

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function normAdv(text?: string): string {
  return (text ?? "")
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokAdv(text: string): string[] {
  return normAdv(text).split(" ").filter(Boolean);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface AdvisoryLookupInput {
  name: string;
  brand?: string;
  categories?: string[];
}

/**
 * Look up advisory "no hechsher needed" guidance for a scanned product.
 * Returns the best matching advisory rule, or null if none applies.
 *
 * This function is intentionally conservative: it requires a confident
 * keyword match before returning a result.
 */
export function lookupAdvisory(input: AdvisoryLookupInput): AdvisoryMatch | null {
  const nameNorm = normAdv(input.name);
  const nameToks = tokAdv(nameNorm);
  const catNorms = (input.categories ?? []).map(normAdv).filter(Boolean);

  if (!nameNorm) return null;

  let best: AdvisoryMatch | null = null;
  let bestScore = 0;

  for (const rule of ADVISORY_RULES) {
    let score = 0;

    // --- Keyword matching ---
    for (const kw of rule.applies_to_keywords) {
      const kwNorm = normAdv(kw);
      const kwToks = tokAdv(kwNorm);

      if (nameNorm === kwNorm) {
        score = Math.max(score, 0.97);
        break;
      }

      // All keyword tokens must appear as whole tokens in the product name.
      // Prevents "zucker" from matching "zuckerfrei" since "zuckerfrei" is one token.
      if (kwToks.length > 0 && kwToks.every((kt) => nameToks.includes(kt))) {
        // Penalise if the product name has many tokens beyond the keyword
        // (more context = more uncertain; e.g. "sea salt with herbs" is less certain
        // than plain "sea salt").
        const extra = nameToks.length - kwToks.length;
        const keywordScore = extra <= 1 ? 0.88 : extra <= 3 ? 0.75 : 0.62;
        score = Math.max(score, keywordScore);
      }
    }

    // --- Category fallback (only when name match is weak) ---
    if (score < 0.65 && catNorms.length > 0) {
      for (const cat of catNorms) {
        for (const ruleCat of rule.categories) {
          const rcNorm = normAdv(ruleCat);
          if (rcNorm && (cat === rcNorm || cat.includes(rcNorm) || rcNorm.includes(cat))) {
            score = Math.max(score, 0.72);
          }
        }
      }
    }

    // Medium-confidence rules require a stronger match
    if (rule.advisory_confidence === "medium" && score < 0.80) {
      score *= 0.85;
    }

    if (score >= 0.65 && score > bestScore) {
      bestScore = score;
      best = { source: rule.source, confidence: score, matchedRule: rule };
    }
  }

  return best;
}
