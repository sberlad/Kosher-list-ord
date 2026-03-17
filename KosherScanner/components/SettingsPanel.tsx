import React from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native";
import { useAppSettings } from "../context/AppSettings";

interface Props {
  visible: boolean;
  onClose: () => void;
}

export default function SettingsPanel({ visible, onClose }: Props) {
  const { pesachMode, setPesachMode, kitniyotAllowed, setKitniyotAllowed } =
    useAppSettings();

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      {/* Tapping the dark backdrop closes the panel */}
      <Pressable style={styles.overlay} onPress={onClose}>
        {/* Tapping inside the sheet does not close it */}
        <Pressable style={styles.sheet} onPress={() => {}}>
          <View style={styles.handle} />

          <Text style={styles.title}>Settings</Text>

          {/* Pesach Mode */}
          <View style={styles.row}>
            <View style={styles.rowText}>
              <Text style={styles.rowLabel}>Pesach Mode</Text>
              <Text style={styles.rowDesc}>
                Show Pesach status on scan results, based on ORD data.
              </Text>
            </View>
            <Switch
              value={pesachMode}
              onValueChange={setPesachMode}
              trackColor={{ false: "#2a2a3a", true: "#4ade8066" }}
              thumbColor={pesachMode ? "#4ade80" : "#6b7280"}
            />
          </View>

          {/* Kitniyot — only visible when Pesach Mode is on */}
          {pesachMode ? (
            <View style={[styles.row, styles.rowKitniyot]}>
              <View style={styles.rowText}>
                <Text style={styles.rowLabel}>Kitniyot permitted</Text>
                <Text style={styles.rowDesc}>
                  Reflects your personal or household practice.{"\n"}
                  Some communities (Sephardic and others) permit kitniyot on
                  Pesach; Ashkenazic tradition generally does not.
                </Text>
                <Text style={styles.rowNote}>
                  The current ORD dataset does not yet classify products as
                  kitniyot. This setting is recorded for when that data
                  becomes available.
                </Text>
              </View>
              <Switch
                value={kitniyotAllowed}
                onValueChange={setKitniyotAllowed}
                trackColor={{ false: "#2a2a3a", true: "#f59e0b66" }}
                thumbColor={kitniyotAllowed ? "#f59e0b" : "#6b7280"}
              />
            </View>
          ) : null}

          <Pressable style={styles.closeBtn} onPress={onClose}>
            <Text style={styles.closeBtnText}>DONE</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(10,10,15,0.8)",
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
    paddingBottom: 44,
  },
  handle: {
    width: 36,
    height: 4,
    backgroundColor: "#ffffff22",
    borderRadius: 2,
    alignSelf: "center",
    marginBottom: 20,
  },
  title: {
    color: "#f8fafc",
    fontSize: 18,
    fontWeight: "700",
    marginBottom: 24,
  },
  row: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 16,
    marginBottom: 20,
    paddingBottom: 20,
    borderBottomWidth: 1,
    borderBottomColor: "#ffffff0d",
  },
  rowKitniyot: {
    marginLeft: 12,
    paddingLeft: 12,
    borderLeftWidth: 2,
    borderLeftColor: "#f59e0b33",
  },
  rowText: {
    flex: 1,
  },
  rowLabel: {
    color: "#e2e8f0",
    fontSize: 15,
    fontWeight: "600",
    marginBottom: 4,
  },
  rowDesc: {
    color: "#8a8f98",
    fontSize: 13,
    lineHeight: 18,
  },
  rowNote: {
    color: "#f59e0b99",
    fontSize: 12,
    lineHeight: 17,
    marginTop: 6,
    fontStyle: "italic",
  },
  closeBtn: {
    borderWidth: 1,
    borderColor: "#ffffff22",
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 4,
  },
  closeBtnText: {
    color: "#cbd5e1",
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 2,
  },
});
