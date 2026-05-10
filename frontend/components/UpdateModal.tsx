import React from "react";
import {
  Modal,
  View,
  Text,
  StyleSheet,
  Image,
  Pressable,
  Platform,
} from "react-native";
import { COLORS, RADIUS, SPACING, SHADOWS } from "../theme";
import { openPlayStore } from "../utils/version-check";
import type { UpdateDecision } from "../utils/version-check";

const MASCOT = require("../assets/images/eilatush-mascot.png");

type Props = {
  decision: UpdateDecision;
  onDismiss: () => void;
};

/** Friendly Hebrew update prompt — soft (dismissible) + force (blocking). */
export default function UpdateModal({ decision, onDismiss }: Props) {
  if (decision.kind === "none") return null;

  const isForce = decision.kind === "force";
  const cfg = decision.config;

  const handleUpdate = () => {
    void openPlayStore(cfg.play_store_url);
  };

  return (
    <Modal
      transparent
      visible
      animationType="fade"
      // On Android, hardware-back should be ignored when force-updating
      onRequestClose={() => {
        if (!isForce) onDismiss();
      }}
      statusBarTranslucent
    >
      <View style={styles.overlay}>
        <View style={styles.card}>
          <View style={styles.mascotRing}>
            <Image source={MASCOT} style={styles.mascot} resizeMode="contain" />
          </View>

          <Text style={styles.title}>גרסה חדשה זמינה!</Text>

          <Text style={styles.message}>
            {cfg.message}
          </Text>

          <View style={styles.versionRow}>
            <Text style={styles.versionLabel}>גרסה נוכחית</Text>
            <Text style={styles.versionCurrent}>{decision.current}</Text>
            <Text style={styles.versionArrow}>←</Text>
            <Text style={styles.versionLatest}>{cfg.latest_version}</Text>
          </View>

          <Pressable
            onPress={handleUpdate}
            style={({ pressed }) => [
              styles.btnPrimary,
              pressed && styles.btnPrimaryPressed,
            ]}
            android_ripple={{ color: "rgba(255,255,255,0.18)" }}
          >
            <Text style={styles.btnPrimaryText}>עדכן/י עכשיו</Text>
          </Pressable>

          {!isForce && (
            <Pressable onPress={onDismiss} style={styles.btnSecondary}>
              <Text style={styles.btnSecondaryText}>אולי מאוחר יותר</Text>
            </Pressable>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: COLORS.overlay,
    alignItems: "center",
    justifyContent: "center",
    padding: SPACING.lg,
  },
  card: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.xl,
    padding: SPACING.lg,
    paddingTop: SPACING.xl + 28, // extra room for the mascot peeking on top
    alignItems: "center",
    ...Platform.select({
      ios: SHADOWS.md,
      android: { elevation: 12 },
    }),
  },
  mascotRing: {
    position: "absolute",
    top: -48,
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: COLORS.surface,
    alignItems: "center",
    justifyContent: "center",
    ...Platform.select({
      ios: SHADOWS.sm,
      android: { elevation: 6 },
    }),
  },
  mascot: {
    width: 84,
    height: 84,
  },
  title: {
    fontSize: 22,
    fontWeight: "900",
    color: COLORS.textPrimary,
    textAlign: "center",
    marginBottom: SPACING.sm,
  },
  message: {
    fontSize: 15,
    lineHeight: 22,
    color: COLORS.textSecondary,
    textAlign: "center",
    marginBottom: SPACING.md,
    paddingHorizontal: SPACING.xs,
  },
  versionRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 8,
    backgroundColor: COLORS.cardHigh,
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.sm,
    borderRadius: RADIUS.pill,
    marginBottom: SPACING.lg,
  },
  versionLabel: {
    fontSize: 12,
    color: COLORS.textMuted,
    fontWeight: "600",
  },
  versionCurrent: {
    fontSize: 13,
    fontWeight: "700",
    color: COLORS.textSecondary,
  },
  versionArrow: {
    fontSize: 13,
    color: COLORS.textMuted,
    marginHorizontal: 2,
  },
  versionLatest: {
    fontSize: 13,
    fontWeight: "900",
    color: COLORS.primary,
  },
  btnPrimary: {
    width: "100%",
    backgroundColor: COLORS.primary,
    paddingVertical: 14,
    borderRadius: RADIUS.lg,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: SPACING.sm,
  },
  btnPrimaryPressed: {
    backgroundColor: COLORS.primaryHover,
  },
  btnPrimaryText: {
    color: COLORS.onPrimary,
    fontSize: 16,
    fontWeight: "900",
  },
  btnSecondary: {
    paddingVertical: SPACING.sm,
    paddingHorizontal: SPACING.md,
  },
  btnSecondaryText: {
    color: COLORS.textMuted,
    fontSize: 14,
    fontWeight: "600",
  },
});
