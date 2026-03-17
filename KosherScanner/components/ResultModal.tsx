import React, { useEffect, useRef } from "react";
import {
  Animated,
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import type { LookupResult, PesachAssessment } from "../services/KosherService";
import { useAppSettings } from "../context/AppSettings";

interface Props {
  visible: boolean;
  result: LookupResult | null;
  barcode?: string;
  onClose: () => void;
  onConfirmYes?: () => void;
  onConfirmNo?: () => void;
}

const GOLD = "#c9a84c";

const STATUS = {
  exact: {
    color: "#4ade80",
    label: "KOSHER CERTIFIED",
    symbol: "✓",
  },
  fuzzy: {
    color: "#f59e0b",
    label: "POSSIBLE MATCH",
    symbol: "~",
  },
  manufacturer: {
    color: "#60a5fa",
    label: "BRAND / FAMILY MATCH",
    symbol: "◎",
  },
  manufacturer_rule: {
    color: "#a78bfa",
    label: "MANUFACTURER RULE",
    symbol: "◈",
  },
  generic_rule: {
    color: GOLD,
    label: "GENERIC ORD RULE",
    symbol: "◌",
  },
  none: {
    color: "#ef4444",
    label: "NOT LISTED",
    symbol: "✗",
  },
} as const;

function StatusSymbol({ type }: { type: keyof typeof STATUS }) {
  const s = STATUS[type];
  const scale = useRef(new Animated.Value(0.5)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.spring(scale, {
        toValue: 1,
        tension: 60,
        friction: 7,
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: 300,
        useNativeDriver: true,
      }),
    ]).start();
  }, [opacity, scale]);

  return (
    <Animated.View
      style={[
        styles.symbolRing,
        {
          borderColor: s.color,
          transform: [{ scale }],
          opacity,
        },
      ]}
    >
      <Text style={[styles.symbolText, { color: s.color }]}>{s.symbol}</Text>
    </Animated.View>
  );
}

function Pill({
  label,
  color,
  note,
}: {
  label: string;
  color: string;
  note?: string;
}) {
  return (
    <View
      style={[
        styles.pill,
        {
          backgroundColor: `${color}18`,
          borderColor: `${color}44`,
        },
      ]}
    >
      <Text style={[styles.pillText, { color }]}>{label}</Text>
      {note ? <Text style={[styles.pillNote, { color: `${color}cc` }]}>{note}</Text> : null}
    </View>
  );
}

function InfoBlock({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  if (!value) return null;

  return (
    <View style={styles.infoBlock}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  );
}

const PESACH_CONFIG: Record<
  PesachAssessment,
  { color: string; label: string; note: string }
> = {
  kosher_lepesach: {
    color: "#4ade80",
    label: "Kosher for Pesach",
    note: "Listed as kosher le-Pesach in the ORD data.",
  },
  kitniyot: {
    color: "#f59e0b",
    label: "Kitniyot",
    note: "This product contains or may contain kitniyot. Suitability depends on your household practice.",
  },
  not_pesach: {
    color: "#ef4444",
    label: "Not kosher for Pesach",
    note: "Listed as not suitable for Pesach in the ORD data.",
  },
  unknown: {
    color: "#6b7280",
    label: "Pesach status unknown",
    note: "The ORD source does not confirm Pesach status for this product. Verify with the certifying authority or your rabbi.",
  },
};

function PesachSection({
  assessment,
  kitniyotAllowed,
}: {
  assessment: PesachAssessment;
  kitniyotAllowed: boolean;
}) {
  const cfg = PESACH_CONFIG[assessment];
  const effectiveAssessment =
    assessment === "kitniyot" && kitniyotAllowed ? "kosher_lepesach" : assessment;
  const effectiveCfg = PESACH_CONFIG[effectiveAssessment];
  const displayCfg = assessment === "kitniyot" ? cfg : effectiveCfg;

  return (
    <View
      style={[
        styles.pesachBox,
        {
          borderColor: `${displayCfg.color}44`,
          backgroundColor: `${displayCfg.color}0d`,
        },
      ]}
    >
      <Text style={styles.pesachTitle}>PESACH MODE</Text>
      <Text style={[styles.pesachLabel, { color: displayCfg.color }]}>
        {displayCfg.label}
        {assessment === "kitniyot" && kitniyotAllowed ? " — permitted (your setting)" : ""}
      </Text>
      <Text style={styles.pesachNote}>{displayCfg.note}</Text>
    </View>
  );
}

export default function ResultModal({
  visible,
  result,
  barcode,
  onClose,
  onConfirmYes,
  onConfirmNo,
}: Props) {
  const slideY = useRef(new Animated.Value(80)).current;
  const opacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!visible) {
      slideY.setValue(80);
      opacity.setValue(0);
      return;
    }

    Animated.parallel([
      Animated.spring(slideY, {
        toValue: 0,
        tension: 65,
        friction: 10,
        useNativeDriver: true,
      }),
      Animated.timing(opacity, {
        toValue: 1,
        duration: 250,
        useNativeDriver: true,
      }),
    ]).start();
  }, [visible, opacity, slideY]);

  const { pesachMode, kitniyotAllowed } = useAppSettings();

  if (!visible || !result) {
    return null;
  }

  const statusConfig = STATUS[result.matchType];
  const matched = result.matchedProduct;
  const off = result.offProduct;

  return (
    <Modal visible={visible} animationType="none" transparent onRequestClose={onClose}>
      <Animated.View style={[styles.overlay, { opacity }]}>
        <Animated.View
          style={[
            styles.sheet,
            {
              transform: [{ translateY: slideY }],
            },
          ]}
        >
          <View style={styles.statusRow}>
            <StatusSymbol type={result.matchType} />
            <View style={styles.statusCopy}>
              <Text style={[styles.statusLabel, { color: statusConfig.color }]}>
                {statusConfig.label}
              </Text>

              {result.matchType !== "none" && typeof result.confidence === "number" ? (
                <Text style={styles.confidenceText}>
                  {Math.round(result.confidence * 100)}% confidence
                </Text>
              ) : null}
            </View>
          </View>

          <View
            style={[
              styles.divider,
              { backgroundColor: `${statusConfig.color}33` },
            ]}
          />

          <ScrollView
            showsVerticalScrollIndicator={false}
            style={styles.scroll}
            contentContainerStyle={styles.scrollContent}
          >
            <InfoBlock label="Source" value={result.source} />
            <InfoBlock label="Barcode" value={barcode} />

            {/* Open Food Facts product info — always show when available */}
            {off ? (
              <View style={styles.offBlock}>
                <Text style={styles.offBlockTitle}>SCANNED PRODUCT</Text>
                {off.imageUrl ? (
                  <Image
                    source={{ uri: off.imageUrl }}
                    style={styles.offImage}
                    resizeMode="contain"
                  />
                ) : null}
                <Text style={styles.offName}>{off.name}</Text>
                {off.brand ? (
                  <Text style={styles.offBrand}>{off.brand}</Text>
                ) : null}
              </View>
            ) : null}

            {matched ? (
              <View style={styles.kosherBlock}>
                {result.matchType === "manufacturer_rule" ? (
                  <Text style={styles.matchedLabel}>ORD MANUFACTURER RULE</Text>
                ) : result.matchType === "generic_rule" ? (
                  <Text style={styles.matchedLabel}>ORD GENERIC RULE</Text>
                ) : result.matchType !== "exact" ? (
                  <Text style={styles.matchedLabel}>MATCHED TO ORD PRODUCT</Text>
                ) : null}

                <Text style={styles.kosherName}>{matched.name}</Text>
                <Text style={styles.kosherMfr}>{matched.manufacturer}</Text>

                {matched.size ? (
                  <Text style={styles.secondaryLine}>Size: {matched.size}</Text>
                ) : null}

                {result.certificate ? (
                  <Text style={styles.cert}>Hechsher: {result.certificate}</Text>
                ) : null}

                {matched.categories?.length ? (
                  <Text style={styles.cats}>{matched.categories.join("  ·  ")}</Text>
                ) : null}
              </View>
            ) : null}

            {pesachMode && result.pesachAssessment !== undefined ? (
              <PesachSection
                assessment={result.pesachAssessment}
                kitniyotAllowed={kitniyotAllowed}
              />
            ) : null}

            {(result.matchType === "exact" ||
              result.matchType === "fuzzy" ||
              result.matchType === "manufacturer" ||
              result.matchType === "manufacturer_rule" ||
              result.matchType === "generic_rule") && (
              <View style={styles.pills}>
                {result.matchType === "manufacturer_rule" ? (
                  <Pill
                    label="Manufacturer Rule"
                    color="#a78bfa"
                    note="This brand has a standing ORD rule covering this product type — not a specific product listing."
                  />
                ) : result.matchType === "generic_rule" ? (
                  <Pill
                    label="Generic ORD Rule"
                    color={GOLD}
                    note="Applies to this product category across all manufacturers — not a specific product listing."
                  />
                ) : null}
              </View>
            )}

            {result.manufacturerProducts &&
            result.manufacturerProducts.length > 1 ? (
              <View style={styles.mfrBlock}>
                <Text style={styles.mfrBlockTitle}>
                  Similar certified products from this manufacturer
                </Text>

                {result.manufacturerProducts.slice(0, 6).map((p) => (
                  <Text key={p.id} style={styles.mfrItem}>
                    · {p.name}
                    {p.size ? ` — ${p.size}` : ""}
                  </Text>
                ))}

                {result.manufacturerProducts.length > 6 ? (
                  <Text style={styles.mfrMore}>
                    +{result.manufacturerProducts.length - 6} more
                  </Text>
                ) : null}
              </View>
            ) : null}

            {result.needsConfirmation ? (
              <View style={styles.confirmBox}>
                <Text style={styles.confirmQ}>
                  Is this the correct product?
                </Text>
                <View style={styles.confirmButtons}>
                  <Pressable
                    style={[styles.confirmBtn, styles.confirmYesBtn]}
                    onPress={() => {
                      onConfirmYes?.();
                      onClose();
                    }}
                  >
                    <Text style={styles.confirmYesBtnText}>Yes, confirm</Text>
                  </Pressable>
                  <Pressable
                    style={[styles.confirmBtn, styles.confirmNoBtn]}
                    onPress={() => {
                      onConfirmNo?.();
                      onClose();
                    }}
                  >
                    <Text style={styles.confirmNoBtnText}>Not a match</Text>
                  </Pressable>
                </View>
              </View>
            ) : null}

            {result.reason ? (
              <View style={styles.noteBox}>
                <Text style={styles.noteLabel}>Note</Text>
                <Text style={styles.noteText}>{result.reason}</Text>
              </View>
            ) : null}

            {result.matchType === "none" ? (
              <View style={styles.notFoundBox}>
                <Text style={styles.notFoundText}>
                  This product is not currently matched in the ORD dataset.
                </Text>
              </View>
            ) : null}
          </ScrollView>

          <Pressable
            style={[styles.closeBtn, { borderColor: `${statusConfig.color}66` }]}
            onPress={onClose}
          >
            <Text style={[styles.closeBtnText, { color: statusConfig.color }]}>
              SCAN ANOTHER
            </Text>
          </Pressable>
        </Animated.View>
      </Animated.View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(10,10,15,0.92)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#111118",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderTopWidth: 1,
    borderLeftWidth: 1,
    borderRightWidth: 1,
    borderColor: "#ffffff0f",
    padding: 24,
    paddingBottom: 36,
    maxHeight: "85%",
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    marginBottom: 20,
  },
  statusCopy: {
    flex: 1,
  },
  symbolRing: {
    width: 56,
    height: 56,
    borderRadius: 28,
    borderWidth: 2,
    justifyContent: "center",
    alignItems: "center",
  },
  symbolText: {
    fontSize: 24,
    fontWeight: "700",
  },
  statusLabel: {
    fontSize: 17,
    fontWeight: "800",
    letterSpacing: 1.5,
  },
  confidenceText: {
    color: "#8a8f98",
    fontSize: 12,
    marginTop: 3,
    letterSpacing: 0.5,
  },
  divider: {
    height: 1,
    marginBottom: 18,
  },
  scroll: {
    maxHeight: 460,
  },
  scrollContent: {
    paddingBottom: 8,
  },
  infoBlock: {
    marginBottom: 14,
  },
  infoLabel: {
    color: "#686f79",
    fontSize: 11,
    letterSpacing: 1.4,
    marginBottom: 4,
    textTransform: "uppercase",
  },
  infoValue: {
    color: "#d7dce2",
    fontSize: 14,
    lineHeight: 20,
  },
  offBlock: {
    backgroundColor: "#ffffff07",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#ffffff12",
    padding: 14,
    marginBottom: 18,
    alignItems: "center",
  },
  offBlockTitle: {
    color: "#686f79",
    fontSize: 10,
    letterSpacing: 1.8,
    marginBottom: 10,
    alignSelf: "flex-start",
  },
  offImage: {
    width: 100,
    height: 100,
    marginBottom: 10,
    borderRadius: 8,
    backgroundColor: "#1a1a24",
  },
  offName: {
    color: "#e2e8f0",
    fontSize: 15,
    fontWeight: "600",
    textAlign: "center",
    lineHeight: 21,
  },
  offBrand: {
    color: "#8a8f98",
    fontSize: 13,
    marginTop: 4,
    textAlign: "center",
  },
  kosherBlock: {
    marginBottom: 18,
  },
  matchedLabel: {
    color: "#666b75",
    fontSize: 10,
    letterSpacing: 2,
    marginBottom: 6,
  },
  kosherName: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 4,
    lineHeight: 24,
  },
  kosherMfr: {
    color: "#9aa1ab",
    fontSize: 13,
    marginBottom: 8,
    letterSpacing: 0.2,
  },
  secondaryLine: {
    color: "#8b9199",
    fontSize: 13,
    marginBottom: 6,
  },
  cert: {
    color: GOLD,
    fontSize: 13,
    marginBottom: 10,
    fontStyle: "italic",
  },
  pills: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 16,
  },
  pill: {
    borderRadius: 6,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  pillText: {
    fontSize: 13,
    fontWeight: "600",
  },
  pillNote: {
    fontSize: 11,
    marginTop: 2,
    lineHeight: 15,
  },
  cats: {
    color: "#6e7480",
    fontSize: 11,
    letterSpacing: 0.6,
    lineHeight: 17,
  },
  mfrBlock: {
    backgroundColor: "#60a5fa0a",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#60a5fa22",
    padding: 14,
    marginBottom: 18,
  },
  mfrBlockTitle: {
    color: "#60a5fa",
    fontSize: 12,
    letterSpacing: 0.8,
    marginBottom: 10,
  },
  mfrItem: {
    color: "#b2b7c0",
    fontSize: 13,
    marginBottom: 5,
    lineHeight: 18,
  },
  mfrMore: {
    color: "#7f8792",
    fontSize: 12,
    marginTop: 4,
  },
  confirmBox: {
    backgroundColor: "#ffffff07",
    borderRadius: 12,
    padding: 16,
    marginBottom: 18,
    alignItems: "center",
  },
  confirmQ: {
    color: "#d0d5dc",
    fontSize: 14,
    textAlign: "center",
    lineHeight: 21,
    letterSpacing: 0.2,
    marginBottom: 14,
  },
  confirmButtons: {
    flexDirection: "row",
    gap: 10,
    width: "100%",
  },
  confirmBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  confirmYesBtn: {
    backgroundColor: "#22c55e22",
    borderWidth: 1,
    borderColor: "#22c55e55",
  },
  confirmYesBtnText: {
    color: "#4ade80",
    fontSize: 14,
    fontWeight: "700",
  },
  confirmNoBtn: {
    backgroundColor: "#ef444415",
    borderWidth: 1,
    borderColor: "#ef444440",
  },
  confirmNoBtnText: {
    color: "#f87171",
    fontSize: 14,
    fontWeight: "700",
  },
  confirmButtons: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 14,
    gap: 10,
  },
  confirmYes: {
    flex: 1,
    backgroundColor: "#22c55e22",
    borderColor: "#22c55e55",
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  confirmYesText: {
    color: "#22c55e",
    fontWeight: "700",
    fontSize: 13,
    letterSpacing: 1,
  },
  confirmNo: {
    flex: 1,
    backgroundColor: "#ef444422",
    borderColor: "#ef444455",
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  confirmNoText: {
    color: "#ef4444",
    fontWeight: "700",
    fontSize: 13,
    letterSpacing: 1,
  },
  noteBox: {
    backgroundColor: "#ffffff07",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#ffffff10",
    padding: 14,
    marginBottom: 18,
  },
  noteLabel: {
    color: "#7f8792",
    fontSize: 11,
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 6,
  },
  noteText: {
    color: "#d5dae1",
    fontSize: 14,
    lineHeight: 21,
  },
  notFoundBox: {
    backgroundColor: "#ef444411",
    borderRadius: 10,
    borderWidth: 1,
    borderColor: "#ef444430",
    padding: 16,
    marginBottom: 18,
  },
  notFoundText: {
    color: "#d1a3a3",
    fontSize: 14,
    lineHeight: 22,
  },
  pesachBox: {
    borderRadius: 10,
    borderWidth: 1,
    padding: 14,
    marginBottom: 18,
  },
  pesachTitle: {
    color: "#686f79",
    fontSize: 10,
    letterSpacing: 1.8,
    marginBottom: 6,
  },
  pesachLabel: {
    fontSize: 15,
    fontWeight: "700",
    marginBottom: 4,
  },
  pesachNote: {
    color: "#8a8f98",
    fontSize: 12,
    lineHeight: 17,
  },
  closeBtn: {
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 14,
  },
  closeBtnText: {
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 2.5,
  },
});
