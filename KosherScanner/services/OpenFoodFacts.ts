const OFF_API = "https://world.openfoodfacts.org/api/v2/product";

export interface OpenFoodFactsProduct {
  barcode: string;
  name: string;
  brand?: string;
  imageUrl?: string;
}

function cleanText(value?: string): string {
  return (value ?? "")
    .replace(/\s+/g, " ")
    .trim();
}

function primaryBrand(brands?: string): string | undefined {
  const cleaned = cleanText(brands);
  if (!cleaned) return undefined;

  const first = cleaned
    .split(",")[0]
    ?.trim();

  return first || undefined;
}

export async function lookupByBarcode(
  barcode: string
): Promise<OpenFoodFactsProduct | null> {
  const safeBarcode = cleanText(barcode);

  if (!safeBarcode) {
    return null;
  }

  try {
    const response = await fetch(
      `${OFF_API}/${encodeURIComponent(
        safeBarcode
      )}.json?fields=product_name,product_name_en,brands,image_front_url,image_url,code`
    );

    if (!response.ok) {
      return null;
    }

    const data = await response.json();

    if (data?.status !== 1 || !data?.product) {
      return null;
    }

    const product = data.product;

    const name = cleanText(
      product.product_name ||
        product.product_name_en ||
        ""
    );

    if (!name) {
      return null;
    }

    return {
      barcode: cleanText(product.code || safeBarcode),
      name,
      brand: primaryBrand(product.brands),
      imageUrl: cleanText(product.image_front_url || product.image_url) || undefined,
    };
  } catch (error) {
    console.error("OpenFoodFacts lookup failed:", error);
    return null;
  }
}