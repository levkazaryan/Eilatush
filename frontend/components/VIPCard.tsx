'use client';

import React, { useEffect, useRef, useState } from "react";
import { View, Text, StyleSheet, Pressable, Animated, Platform, Easing, Image } from "react-native";

// Premium gold dolphin asset (user-provided)
const DOLPHIN_IMG = require("../assets/images/gold-dolphin.png");

// ───── Premium palette: matte black + hairline gold ─────
const GOLD = "#D4AF37";          // primary gold
const GOLD_LIGHT = "#EBC868";    // highlight
const INK = "#0A0A0B";           // matte black
const HAIRLINE = "rgba(212,175,55,0.55)"; // thin gold line
const HAIRLINE_SOFT = "rgba(212,175,55,0.25)"; // softer thin gold

type Props = {
  fullName?: string;
  memberNumber?: string;
  dob?: string;
  expiryDate?: string;
  preview?: boolean;
  interactive?: boolean;
};

function formatHebDate(iso?: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso + (iso.length === 10 ? "T00:00:00Z" : ""));
    if (isNaN(d.getTime())) return iso;
    const dd = String(d.getUTCDate()).padStart(2, "0");
    const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    const yy = String(d.getUTCFullYear()).slice(2);
    return `${dd}/${mm}/${yy}`;
  } catch {
    return iso;
  }
}

function formatExpiry(iso?: string): string {
  if (!iso) return "MM/YY";
  try {
    const d = new Date(iso + (iso.length === 10 ? "T00:00:00Z" : ""));
    if (isNaN(d.getTime())) return "MM/YY";
    const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    const yy = String(d.getUTCFullYear()).slice(2);
    return `${mm}/${yy}`;
  } catch {
    return "MM/YY";
  }
}

// ───── Dolphin (gold image, user-provided premium asset) ─────
function Dolphin({
  size = 120,
  opacity = 1,
}: { size?: number; opacity?: number; gradient?: boolean }) {
  return (
    <Image
      source={DOLPHIN_IMG}
      style={{ width: size, height: size, opacity }}
      resizeMode="contain"
    />
  );
}

// ───── Tiny corner ornament (thin gold L) ─────
function CornerOrn({ position }: { position: "tl" | "tr" | "bl" | "br" }) {
  const map = {
    tl: { top: 10, left: 10, borderTopWidth: 1, borderLeftWidth: 1, borderTopLeftRadius: 4 },
    tr: { top: 10, right: 10, borderTopWidth: 1, borderRightWidth: 1, borderTopRightRadius: 4 },
    bl: { bottom: 10, left: 10, borderBottomWidth: 1, borderLeftWidth: 1, borderBottomLeftRadius: 4 },
    br: { bottom: 10, right: 10, borderBottomWidth: 1, borderRightWidth: 1, borderBottomRightRadius: 4 },
  } as const;
  return (
    <View
      pointerEvents="none"
      style={[
        { position: "absolute", width: 18, height: 18, borderColor: HAIRLINE },
        map[position],
      ]}
    />
  );
}

export default function VIPCard({
  fullName,
  memberNumber,
  dob,
  expiryDate,
  preview = false,
  interactive = true,
}: Props) {
  const [flipped, setFlipped] = useState(false);
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(anim, {
      toValue: flipped ? 1 : 0,
      duration: 650,
      easing: Easing.inOut(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [flipped, anim]);

  const frontRotate = anim.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "180deg"] });
  const backRotate = anim.interpolate({ inputRange: [0, 1], outputRange: ["180deg", "360deg"] });
  const frontOpacity = anim.interpolate({ inputRange: [0, 0.5, 0.5001, 1], outputRange: [1, 1, 0, 0] });
  const backOpacity = anim.interpolate({ inputRange: [0, 0.4999, 0.5, 1], outputRange: [0, 0, 1, 1] });

  const handlePress = () => {
    if (!interactive) return;
    setFlipped((f) => !f);
  };

  const displayName = preview ? "שמכם יופיע כאן" : (fullName || "—");
  const displayNumber = preview ? "VIP-2026-0000" : (memberNumber || "—");
  const displayExpiry = preview ? "06/26" : formatExpiry(expiryDate);
  const displayDob = preview ? "—" : formatHebDate(dob);

  return (
    <Pressable onPress={handlePress} style={styles.wrap} accessibilityLabel="כרטיס VIP — לחץ להפיכה">
      {/* ╔══════════════ FRONT (user-designed image) ══════════════╗ */}
      <Animated.View
        pointerEvents={flipped ? "none" : "auto"}
        style={[
          styles.cardAbs,
          { transform: [{ perspective: 1200 }, { rotateY: frontRotate }], opacity: frontOpacity },
        ]}
      >
        <View style={styles.cardInner}>
          {/* Pre-designed VIP card front image */}
          <Image
            source={require("../assets/images/vip-card-front.png")}
            style={styles.cardFrontImg}
            resizeMode="cover"
          />
          {/* Bottom-left flip hint overlay (kept exactly as before) */}
          {interactive ? (
            <View style={styles.flipHintWrap} pointerEvents="none">
              <Text style={styles.flipHintOnImg}>↻ לחצו להפיכת הכרטיס</Text>
            </View>
          ) : null}
        </View>
      </Animated.View>

      {/* ╔══════════════ BACK ══════════════╗ */}
      <Animated.View
        pointerEvents={flipped ? "auto" : "none"}
        style={[
          styles.cardAbs,
          { transform: [{ perspective: 1200 }, { rotateY: backRotate }], opacity: backOpacity },
        ]}
      >
        <View style={[styles.cardInner, styles.backInner]}>
          {/* Background image (gold dolphin + gold borders + textured corners) */}
          <Image
            source={require("../assets/images/vip-card-back-bg.png")}
            style={styles.cardBackBgImg}
            resizeMode="cover"
          />
          {/* Dark overlay so the text stays readable above the artwork */}
          <View pointerEvents="none" style={styles.backDarkOverlay} />

          {/* Header strip */}
          <View style={styles.backHeader}>
            <Text style={styles.backTitle}>תושב אילת · VIP</Text>
            <View style={styles.backNumChip}>
              <Text style={styles.backNumText}>{displayNumber}</Text>
            </View>
          </View>

          {/* Thin gold separator under header */}
          <View style={styles.thinSep} />

          {/* Name label */}
          <View style={styles.nameRow}>
            <Text style={styles.fieldLabel}>שם החבר</Text>
            <Text style={styles.nameValue} numberOfLines={1}>{displayName}</Text>
          </View>

          {/* Details grid — only DOB and Expiry */}
          <View style={styles.detailsGrid}>
            <Detail label="תאריך לידה" value={displayDob} />
            <Detail label="תקף עד" value={displayExpiry} highlight />
          </View>

          {/* Bottom row — in normal flow, pushed to bottom */}
          <View style={styles.backBottomRow}>
            <Text style={styles.flipHint}>↻ חזרה לחזית</Text>
            <Text style={styles.appUrl}>EILATUSH.APP</Text>
          </View>
        </View>
      </Animated.View>
    </Pressable>
  );
}

function Detail({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <View style={styles.detailCell}>
      <Text style={styles.detailLabel}>{label}</Text>
      <Text style={[styles.detailValue, highlight && { color: GOLD_LIGHT }]} numberOfLines={1}>
        {value}
      </Text>
    </View>
  );
}

const CARD_RADIUS = 20;

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    maxWidth: 380,
    aspectRatio: 1.586, // ISO/IEC 7810 ID-1 (credit card)
    alignSelf: "center",
  },
  cardAbs: {
    position: "absolute",
    top: 0, left: 0, right: 0, bottom: 0,
    backfaceVisibility: "hidden" as any,
  },
  cardInner: {
    flex: 1,
    borderRadius: CARD_RADIUS,
    backgroundColor: INK,
    overflow: "hidden",
    paddingTop: 18,
    paddingHorizontal: 18,
    paddingBottom: 14,
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOpacity: 0.6,
        shadowRadius: 24,
        shadowOffset: { width: 0, height: 14 },
      },
      android: { elevation: 14 },
      default: {
        // @ts-ignore — web only
        boxShadow: "0 20px 40px rgba(0,0,0,0.55), 0 0 0 0.5px rgba(212,175,55,0.15)",
      },
    }),
  },

  // ─── Pre-designed front image fills the entire card ───
  cardFrontImg: {
    position: "absolute",
    top: 0, left: 0, right: 0, bottom: 0,
    width: "100%",
    height: "100%",
    borderRadius: CARD_RADIUS,
  },

  // Bottom-left flip hint overlay on top of the image
  flipHintWrap: {
    position: "absolute",
    left: 14,
    bottom: 10,
    zIndex: 5,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    backgroundColor: "rgba(0,0,0,0.45)",
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOpacity: 0.6,
        shadowRadius: 4,
        shadowOffset: { width: 0, height: 1 },
      },
      default: { boxShadow: "0 1px 4px rgba(0,0,0,0.6)" } as any,
    }),
  },
  flipHintOnImg: {
    color: GOLD,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.4,
    opacity: 0.95,
  },

  // ─── Hairline gold frames ───
  outerHairline: {
    position: "absolute",
    top: 0, left: 0, right: 0, bottom: 0,
    borderRadius: CARD_RADIUS,
    borderWidth: 1,
    borderColor: HAIRLINE,
  },
  innerHairline: {
    position: "absolute",
    top: 6, left: 6, right: 6, bottom: 6,
    borderRadius: CARD_RADIUS - 6,
    borderWidth: 0.6,
    borderColor: HAIRLINE_SOFT,
  },

  // ─── Top row ───
  topRow: {
    flexDirection: "row-reverse",
    alignItems: "flex-start",
    justifyContent: "space-between",
    zIndex: 3,
    marginTop: 4,
  },
  brandRight: {
    alignItems: "flex-end",
  },
  brandTitleHe: {
    color: "#FFFFFF",
    fontSize: 18,
    fontWeight: "900",
    letterSpacing: 0.6,
    textAlign: "right",
  },
  brandLine: {
    height: 0.8,
    width: 90,
    backgroundColor: GOLD,
    opacity: 0.75,
    marginTop: 5,
    marginBottom: 5,
    alignSelf: "flex-end",
  },
  brandSub: {
    color: GOLD,
    fontSize: 8.5,
    fontWeight: "700",
    letterSpacing: 2.4,
    opacity: 0.85,
    textAlign: "right",
  },
  statusBox: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 6,
    paddingVertical: 4,
    paddingHorizontal: 9,
    borderRadius: 999,
    borderWidth: 0.8,
    borderColor: HAIRLINE,
    backgroundColor: "rgba(212,175,55,0.05)",
  },
  statusDot: {
    width: 5, height: 5, borderRadius: 3, backgroundColor: GOLD_LIGHT,
    ...Platform.select({
      ios: { shadowColor: GOLD_LIGHT, shadowOpacity: 0.8, shadowRadius: 4, shadowOffset: { width: 0, height: 0 } },
      default: { boxShadow: "0 0 6px rgba(235,200,104,0.85)" } as any,
    }),
  },
  statusText: {
    color: GOLD_LIGHT,
    fontSize: 8.5,
    fontWeight: "800",
    letterSpacing: 2,
  },

  // ─── Hero dolphin ───
  heroWrap: {
    position: "absolute",
    top: "50%",
    right: "10%",
    marginTop: -80, // center vertically (half of size=160)
    zIndex: 2,
    ...Platform.select({
      ios: {
        shadowColor: GOLD,
        shadowOpacity: 0.45,
        shadowRadius: 18,
        shadowOffset: { width: 0, height: 0 },
      },
      default: { filter: "drop-shadow(0 0 16px rgba(212,175,55,0.4))" } as any,
    }),
  },

  // ─── VIP plate (bottom-left) ───
  vipPlateWrap: {
    position: "absolute",
    left: 22,
    bottom: 50,
    zIndex: 4,
  },
  vipPlate: {
    borderWidth: 1,
    borderColor: GOLD,
    paddingHorizontal: 14,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: "rgba(212,175,55,0.06)",
  },
  vipPlateText: {
    color: GOLD_LIGHT,
    fontSize: 26,
    fontWeight: "900",
    letterSpacing: 5,
    lineHeight: 32,
  },

  // ─── Divider & bottom row ───
  divider: {
    position: "absolute",
    left: 22,
    right: 22,
    bottom: 38,
    height: 0.6,
    backgroundColor: HAIRLINE_SOFT,
  },
  bottomRow: {
    position: "absolute",
    left: 22,
    right: 22,
    bottom: 14,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
  },
  flipHint: {
    color: GOLD,
    fontSize: 9.5,
    opacity: 0.75,
    fontWeight: "600",
    letterSpacing: 0.4,
  },
  appUrl: {
    color: GOLD,
    fontSize: 9.5,
    fontWeight: "800",
    letterSpacing: 2.8,
    opacity: 0.85,
  },

  // ─── BACK ───
  backInner: {
    paddingTop: 14,
    paddingBottom: 12,
  },
  // Background artwork (gold dolphin + frame)
  cardBackBgImg: {
    position: "absolute",
    top: 0, left: 0, right: 0, bottom: 0,
    width: "100%",
    height: "100%",
    borderRadius: CARD_RADIUS,
  },
  // Dark overlay to keep the member info readable above the artwork
  backDarkOverlay: {
    position: "absolute",
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.55)",
    borderRadius: CARD_RADIUS,
  },
  watermarkWrap: {
    position: "absolute",
    top: "50%",
    left: 0,
    right: 0,
    alignItems: "center",
    transform: [{ translateY: -90 }],
  },
  backHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 2,
  },
  backTitle: {
    color: GOLD,
    fontSize: 13,
    fontWeight: "900",
    letterSpacing: 2.4,
    textAlign: "right",
  },
  backNumChip: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 0.8,
    borderColor: GOLD,
    backgroundColor: "rgba(212,175,55,0.05)",
  },
  backNumText: {
    color: GOLD_LIGHT,
    fontSize: 10.5,
    fontWeight: "800",
    letterSpacing: 1.5,
  },
  thinSep: {
    marginTop: 8,
    height: 0.6,
    backgroundColor: HAIRLINE_SOFT,
  },
  nameRow: {
    marginTop: 8,
    alignItems: "flex-start",
  },
  fieldLabel: {
    color: GOLD,
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 1.5,
    opacity: 0.85,
    textAlign: "right",
  },
  nameValue: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "800",
    textAlign: "right",
    marginTop: 2,
    letterSpacing: 0.3,
  },
  detailsGrid: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    marginTop: 10,
    gap: 6,
  },
  detailCell: {
    flexBasis: "47%",
    flexGrow: 1,
    borderWidth: 0.6,
    borderColor: HAIRLINE_SOFT,
    borderRadius: 8,
    paddingHorizontal: 9,
    paddingVertical: 5,
    backgroundColor: "rgba(17,17,20,0.85)",
  },
  detailLabel: {
    color: GOLD,
    fontSize: 8.5,
    fontWeight: "700",
    letterSpacing: 1.2,
    opacity: 0.85,
    textAlign: "right",
  },
  detailValue: {
    color: "#fff",
    fontSize: 12.5,
    fontWeight: "800",
    textAlign: "right",
    marginTop: 1,
  },
  backBottomRow: {
    marginTop: "auto",
    paddingTop: 8,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
  },
});
