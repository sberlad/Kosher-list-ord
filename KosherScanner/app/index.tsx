import React, { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";

import ResultModal from "../components/ResultModal";
import SettingsPanel from "../components/SettingsPanel";
import { lookupByBarcode } from "../services/OpenFoodFacts";
import {
  lookupProduct,
  loadKosherData,
  getProductById,
  getPesachAssessment,
  type LookupResult,
} from "../services/KosherService";
import {
  lookupConfirmedBarcode,
  confirmBarcode,
  rejectBarcode,
} from "../services/BarcodeConfirmationApi";

type ScanResultState = LookupResult | null;

const SCAN_COOLDOWN_MS = 1200;
const RESULT_CACHE_TTL = 24 * 60 * 60 * 1000;

type ResultCacheEntry = {
  result: LookupResult;
  timestamp: number;
};

const barcodeResultCache = new Map<string, ResultCacheEntry>();

function createUnknownResult(reason: string): LookupResult {
  return {
    status: "unknown",
    matchType: "none",
    confidence: 0,
    source: "ORD",
    reason,
  };
}

export default function HomeScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [settingsPanelVisible, setSettingsPanelVisible] = useState(false);
  const [result, setResult] = useState<ScanResultState>(null);
  const [lastBarcode, setLastBarcode] = useState<string | null>(null);

  const cooldown = useRef(false);

  const permissionState = useMemo(() => {
    if (!permission) return "loading";
    if (permission.granted) return "granted";
    return "denied";
  }, [permission]);

  const openResult = useCallback((lookupResult: LookupResult, barcode?: string) => {
    setResult(lookupResult);
    if (barcode) {
      setLastBarcode(barcode);
    }
    setModalVisible(true);
  }, []);

  const resetCooldownLater = useCallback(() => {
    setTimeout(() => {
      cooldown.current = false;
    }, SCAN_COOLDOWN_MS);
  }, []);

  const getCachedResult = useCallback((barcode: string): LookupResult | null => {
    const cached = barcodeResultCache.get(barcode);
    if (!cached) return null;

    if (Date.now() - cached.timestamp > RESULT_CACHE_TTL) {
      barcodeResultCache.delete(barcode);
      return null;
    }

    return cached.result;
  }, []);

  const setCachedResult = useCallback((barcode: string, value: LookupResult) => {
    barcodeResultCache.set(barcode, {
      result: value,
      timestamp: Date.now(),
    });
  }, []);

  const handleBarcodeScanned = useCallback(
    async ({ data }: { data: string }) => {
      if (!data || cooldown.current || loading) {
        return;
      }

      cooldown.current = true;
      setLoading(true);
      setLastBarcode(data);

      try {
        const cachedResult = getCachedResult(data);
        if (cachedResult) {
          openResult(cachedResult, data);
          return;
        }

        // 1. Trusted barcode confirmation lookup
        const confirmed = await lookupConfirmedBarcode(data);

        if (confirmed?.product_id) {
          const kosherData = await loadKosherData();
          const resolved = getProductById(kosherData.products, confirmed.product_id);

          const trustedResult: LookupResult = {
            status: "kosher",
            matchType: "exact",
            confidence: 1,
            source: "ORD",
            certificate: resolved?.certificate,
            pesachAssessment: getPesachAssessment(resolved),
            reason: `Trusted barcode match (${confirmed.confirmations ?? 0} confirmations).`,
            matchedProduct: resolved
              ? {
                  id: resolved.id,
                  name: resolved.display_name || resolved.name,
                  manufacturer: resolved.manufacturer,
                  size: resolved.size,
                  categories: resolved.categories,
                }
              : {
                  id: confirmed.product_id,
                  name: confirmed.product_id,
                  manufacturer: "Confirmed barcode match",
                },
          };

          setCachedResult(data, trustedResult);
          openResult(trustedResult, data);
          return;
        }

        // 2. Open Food Facts fallback
        const offProduct = await lookupByBarcode(data);

        if (!offProduct) {
          const unknown = createUnknownResult("Product not found in Open Food Facts.");
          setCachedResult(data, unknown);
          openResult(unknown, data);
          return;
        }

        // 3. ORD fuzzy/exact/manufacturer lookup
        const kosherResult = await lookupProduct({
          barcode: data,
          name: offProduct.name,
          brand: offProduct.brand,
        });

        // Attach OFF product info so the modal can display scanned product details
        const enrichedResult: LookupResult = {
          ...kosherResult,
          offProduct: {
            name: offProduct.name,
            brand: offProduct.brand,
            imageUrl: offProduct.imageUrl,
          },
        };

        setCachedResult(data, enrichedResult);
        openResult(enrichedResult, data);
      } catch (error) {
        console.error("Barcode lookup failed:", error);
        openResult(createUnknownResult("Lookup failed."), data);
      } finally {
        setLoading(false);
        resetCooldownLater();
      }
    },
    [getCachedResult, loading, openResult, resetCooldownLater, setCachedResult]
  );

  const handleRequestPermission = useCallback(async () => {
    try {
      const response = await requestPermission();
      if (!response.granted) {
        Alert.alert(
          "Camera permission needed",
          "Please allow camera access to scan barcodes."
        );
      }
    } catch (error) {
      console.error("Permission request failed:", error);
      Alert.alert("Permission error", "Could not request camera permission.");
    }
  }, [requestPermission]);

  // All hooks must be declared before any conditional return
  const handleConfirmYes = useCallback(async () => {
    if (!lastBarcode || !result?.matchedProduct?.id) return;

    try {
      await confirmBarcode(lastBarcode, result.matchedProduct.id);
    } catch (err) {
      console.error("Confirm barcode failed:", err);
    }
  }, [lastBarcode, result]);

  const handleConfirmNo = useCallback(async () => {
    if (!lastBarcode || !result?.matchedProduct?.id) return;

    try {
      await rejectBarcode(lastBarcode, result.matchedProduct.id);
    } catch (err) {
      console.error("Reject barcode failed:", err);
    }
  }, [lastBarcode, result]);

  if (permissionState === "loading") {
    return (
      <SafeAreaView style={styles.centeredScreen}>
        <ActivityIndicator size="large" />
        <Text style={styles.helperText}>Checking camera permission…</Text>
      </SafeAreaView>
    );
  }

  if (permissionState === "denied") {
    return (
      <SafeAreaView style={styles.centeredScreen}>
        <Text style={styles.title}>Camera access required</Text>
        <Text style={styles.helperText}>
          This app needs camera access to scan product barcodes.
        </Text>
        <Pressable style={styles.primaryButton} onPress={handleRequestPermission}>
          <Text style={styles.primaryButtonText}>Grant camera access</Text>
        </Pressable>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerRow}>
          <Text style={styles.title}>Kosher Scanner</Text>
          <Pressable
            style={styles.gearBtn}
            onPress={() => setSettingsPanelVisible(true)}
            accessibilityLabel="Open settings"
            accessibilityRole="button"
          >
            <Text style={styles.gearIcon}>⚙</Text>
          </Pressable>
        </View>
        <Text style={styles.subtitle}>
          Scan a product barcode to check it against the ORD list.
        </Text>
      </View>

      <View style={styles.cameraFrame}>
        <CameraView
          style={StyleSheet.absoluteFillObject}
          facing="back"
          barcodeScannerSettings={{
            barcodeTypes: [
              "ean13",
              "ean8",
              "upc_a",
              "upc_e",
              "code128",
              "code39",
              "qr",
            ],
          }}
          onBarcodeScanned={handleBarcodeScanned}
        />

        <View pointerEvents="none" style={styles.overlay}>
          <View style={styles.overlayShade} />
          <View style={styles.scanRow}>
            <View style={styles.overlayShade} />
            <View style={styles.scanWindow} />
            <View style={styles.overlayShade} />
          </View>
          <View style={styles.overlayShade} />
        </View>

        {loading && (
          <View style={styles.loadingOverlay}>
            <ActivityIndicator size="large" color="#fff" />
            <Text style={styles.loadingText}>Checking product…</Text>
          </View>
        )}
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          {lastBarcode ? `Last scanned: ${lastBarcode}` : "Ready to scan"}
        </Text>
      </View>

      <ResultModal
        visible={modalVisible}
        result={result}
        barcode={lastBarcode ?? undefined}
        onClose={() => setModalVisible(false)}
        onConfirmYes={handleConfirmYes}
        onConfirmNo={handleConfirmNo}
      />

      <SettingsPanel
        visible={settingsPanelVisible}
        onClose={() => setSettingsPanelVisible(false)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f172a",
  },
  centeredScreen: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
    backgroundColor: "#0f172a",
  },
  header: {
    paddingHorizontal: 20,
    paddingTop: 20,
    paddingBottom: 16,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 8,
  },
  title: {
    color: "#f8fafc",
    fontSize: 28,
    fontWeight: "700",
  },
  gearBtn: {
    padding: 6,
  },
  gearIcon: {
    fontSize: 22,
    color: "#94a3b8",
  },
  subtitle: {
    color: "#cbd5e1",
    fontSize: 15,
    lineHeight: 22,
  },
  helperText: {
    color: "#cbd5e1",
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center",
    marginTop: 12,
    marginBottom: 20,
    maxWidth: 360,
  },
  cameraFrame: {
    flex: 1,
    marginHorizontal: 16,
    marginBottom: 16,
    borderRadius: 20,
    overflow: "hidden",
    backgroundColor: "#111827",
    position: "relative",
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
  },
  overlayShade: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.55)",
  },
  scanRow: {
    height: 220,
    flexDirection: "row",
  },
  scanWindow: {
    width: "78%",
    borderWidth: 2,
    borderColor: "#f8fafc",
    borderRadius: 18,
    backgroundColor: "transparent",
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(15, 23, 42, 0.55)",
    alignItems: "center",
    justifyContent: "center",
    gap: 12,
  },
  loadingText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  footer: {
    paddingHorizontal: 20,
    paddingBottom: 20,
  },
  footerText: {
    color: "#cbd5e1",
    fontSize: 14,
    textAlign: "center",
  },
  primaryButton: {
    backgroundColor: "#22c55e",
    paddingHorizontal: 18,
    paddingVertical: 14,
    borderRadius: 12,
  },
  primaryButtonText: {
    color: "#052e16",
    fontSize: 16,
    fontWeight: "700",
  },
});
