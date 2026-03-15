const API_BASE = "https://api.samuelberlad.com/kosher_scanner";

export interface BarcodeConfirmationLookup {
  product_id: string | null;
  confirmations?: number;
}

export async function lookupConfirmedBarcode(
  barcode: string
): Promise<BarcodeConfirmationLookup | null> {
  try {
    const response = await fetch(
      `${API_BASE}/get_barcode.php?barcode=${encodeURIComponent(barcode)}`
    );

    if (!response.ok) {
      return null;
    }

    const data = (await response.json()) as BarcodeConfirmationLookup;
    return data;
  } catch (error) {
    console.error("Confirmed barcode lookup failed:", error);
    return null;
  }
}

export async function confirmBarcodeMatch(
  barcode: string,
  productId: string
): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/confirm_barcode.php`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        barcode,
        product_id: productId,
      }),
    });

    if (!response.ok) {
      return false;
    }

    const data = await response.json();
    return data?.status === "ok";
  } catch (error) {
    console.error("Confirm barcode match failed:", error);
    return false;
  }
}