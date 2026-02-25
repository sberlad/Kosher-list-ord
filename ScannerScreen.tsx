/**
 * ScannerScreen.tsx
 *
 * Barcode scanner screen using react-native-vision-camera.
 * Scans EAN/UPC barcodes → queries KosherService → shows result.
 *
 * Dependencies (add to package.json):
 *   react-native-vision-camera
 *   vision-camera-code-scanner
 *   react-native-community/netinfo
 *   @react-native-async-storage/async-storage
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import {
  Camera,
  useCameraDevices,
  useFrameProcessor,
} from "react-native-vision-camera";
import { scanBarcodes, BarcodeFormat } from "vision-camera-code-scanner";
import { runOnJS } from "react-native-reanimated";
import { kosherService, LookupResult } from "../services/KosherService";
import ResultModal from "../components/ResultModal";

export default function ScannerScreen() {
  const devices = useCameraDevices();
  const device = devices.back;
  const camera = useRef<Camera>(null);

  const [hasPermission, setHasPermission] = useState(false);
  const [scanning, setScanning] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LookupResult | null>(null);
  const [lastBarcode, setLastBarcode] = useState<string | null>(null);

  // Request camera permission on mount
  useEffect(() => {
    (async () => {
      const status = await Camera.requestCameraPermission();
      setHasPermission(status === "authorized");
    })();
  }, []);

  const handleBarcode = useCallback(
    async (barcode: string) => {
      if (!scanning || loading || barcode === lastBarcode) return;

      setLastBarcode(barcode);
      setScanning(false);
      setLoading(true);

      try {
        const res = await kosherService.lookupBarcode(barcode);
        setResult(res);
      } catch (e) {
        console.error("Lookup error:", e);
        setResult({ found: false });
      } finally {
        setLoading(false);
      }
    },
    [scanning, loading, lastBarcode]
  );

  // Frame processor — runs on every camera frame
  const frameProcessor = useFrameProcessor((frame) => {
    "worklet";
    const barcodes = scanBarcodes(frame, [
      BarcodeFormat.EAN_13,
      BarcodeFormat.EAN_8,
      BarcodeFormat.UPC_A,
      BarcodeFormat.UPC_E,
    ]);
    if (barcodes.length > 0 && barcodes[0].rawValue) {
      runOnJS(handleBarcode)(barcodes[0].rawValue);
    }
  }, [handleBarcode]);

  const resetScan = () => {
    setResult(null);
    setLastBarcode(null);
    setScanning(true);
  };

  if (!hasPermission) {
    return (
      <View style={styles.center}>
        <Text style={styles.permText}>Camera permission required</Text>
      </View>
    );
  }

  if (!device) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2A6049" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Camera
        ref={camera}
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={scanning && !loading}
        frameProcessor={frameProcessor}
        frameProcessorFps={5}
      />

      {/* Viewfinder overlay */}
      <View style={styles.overlay}>
        <View style={styles.viewfinder} />
        <Text style={styles.hint}>Point at a barcode</Text>
      </View>

      {/* Loading spinner */}
      {loading && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color="#fff" />
          <Text style={styles.loadingText}>Checking kosher status…</Text>
        </View>
      )}

      {/* Result modal */}
      {result && (
        <ResultModal result={result} onDismiss={resetScan} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  permText: { color: "#fff", fontSize: 16 },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: "center",
    alignItems: "center",
  },
  viewfinder: {
    width: 260,
    height: 160,
    borderWidth: 2,
    borderColor: "#2A6049",
    borderRadius: 12,
    backgroundColor: "transparent",
  },
  hint: {
    marginTop: 16,
    color: "#fff",
    fontSize: 14,
    opacity: 0.8,
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.7)",
    justifyContent: "center",
    alignItems: "center",
    gap: 16,
  },
  loadingText: { color: "#fff", fontSize: 16 },
});
