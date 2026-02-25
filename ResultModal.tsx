/**
 * ResultModal.tsx
 *
 * Displays the kosher lookup result clearly:
 *   ✅ Green  — product found and kosher
 *   ⚠️ Amber  — manufacturer is kosher but specific product not listed
 *   ❌ Red    — not found in the kosher list
 */

import React from "react";
import {
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { LookupResult, DairyStatus } from "../services/KosherService";

interface Props {
  result: LookupResult;
  onDismiss: () => void;
}

const DAIRY_LABELS: Record<DairyStatus, string> = {
  milchig: "🥛 Milchig (Dairy)",
  parve: "⚪ Parve",
  fleischig: "🥩 Fleischig (Meat)",
  unknown: "",
};

export default function ResultModal({ result, onDismiss }: Props) {
  const status = getStatus(result);

  return (
    <Modal
      transparent
      animationType="slide"
      visible={true}
      onRequestClose={onDismiss}
    >
      <View style={styles.backdrop}>
        <View style={[styles.card, { borderColor: status.color }]}>
          {/* Status icon + title */}
          <Text style={styles.icon}>{status.icon}</Text>
          <Text style={[styles.title, { color: status.color }]}>
            {status.title}
          </Text>

          {/* Scanned product info from Open Food Facts */}
          {result.barcode_product_name && (
            <View style={styles.section}>
              <Text style={styles.label}>Scanned product</Text>
              <Text style={styles.value}>{result.barcode_product_name}</Text>
              {result.barcode_manufacturer && (
                <Text style={styles.subValue}>{result.barcode_manufacturer}</Text>
              )}
            </View>
          )}

          {/* Matched kosher product details */}
          {result.product && (
            <View style={styles.section}>
              <Text style={styles.label}>ORD listing</Text>
              <Text style={styles.value}>{result.product.name}</Text>
              <Text style={styles.subValue}>{result.product.manufacturer}</Text>

              {result.product.dairy_status !== "unknown" && (
                <Text style={styles.badge}>
                  {DAIRY_LABELS[result.product.dairy_status]}
                </Text>
              )}

              {result.product.certificate.length > 0 && (
                <Text style={styles.cert}>
                  🏅 {result.product.certificate}
                </Text>
              )}

              {result.product.pessach === "kosher_lepessach" && (
                <Text style={styles.pessach}>✡️ Kosher lePessach</Text>
              )}

              {result.product.categories.length > 0 && (
                <Text style={styles.categories}>
                  {result.product.categories.join(" · ")}
                </Text>
              )}
            </View>
          )}

          {/* Manufacturer-only match note */}
          {result.manufacturer_match && (
            <View style={styles.section}>
              <Text style={styles.note}>{result.manufacturer_match.note}</Text>
            </View>
          )}

          {/* Not found */}
          {!result.found && !result.manufacturer_match && (
            <View style={styles.section}>
              <Text style={styles.note}>
                This product is not on the ORD kosher list. It may still be
                certified by another authority — look for a hechsher on the
                packaging.
              </Text>
            </View>
          )}

          <TouchableOpacity style={styles.button} onPress={onDismiss}>
            <Text style={styles.buttonText}>Scan Again</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

type StatusInfo = { icon: string; title: string; color: string };

function getStatus(result: LookupResult): StatusInfo {
  if (result.found) {
    return { icon: "✅", title: "Kosher (ORD certified)", color: "#2A6049" };
  }
  if (result.manufacturer_match) {
    return {
      icon: "⚠️",
      title: "Manufacturer is certified",
      color: "#B87C00",
    };
  }
  return { icon: "❌", title: "Not found on ORD list", color: "#C0392B" };
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "flex-end",
  },
  card: {
    backgroundColor: "#fff",
    borderRadius: 20,
    borderTopWidth: 6,
    margin: 12,
    padding: 24,
    gap: 8,
  },
  icon: { fontSize: 48, textAlign: "center" },
  title: { fontSize: 22, fontWeight: "700", textAlign: "center" },
  section: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "#eee",
    gap: 4,
  },
  label: { fontSize: 11, color: "#999", textTransform: "uppercase" },
  value: { fontSize: 17, fontWeight: "600", color: "#111" },
  subValue: { fontSize: 14, color: "#555" },
  badge: { fontSize: 14, marginTop: 6 },
  cert: { fontSize: 13, color: "#555" },
  pessach: { fontSize: 13, color: "#2A6049" },
  categories: { fontSize: 12, color: "#999", marginTop: 4 },
  note: { fontSize: 14, color: "#555", lineHeight: 20 },
  button: {
    backgroundColor: "#2A6049",
    borderRadius: 12,
    paddingVertical: 14,
    marginTop: 16,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "600" },
});
