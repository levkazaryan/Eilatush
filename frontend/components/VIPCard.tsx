'use client';

import React, { useEffect, useRef, useState } from "react";
import { View, Text, StyleSheet, Pressable, Animated, Platform, Easing } from "react-native";
import Svg, { Path, Defs, LinearGradient as SvgGradient, Stop, G } from "react-native-svg";

// ───── Premium palette: matte black + hairline gold ─────
const GOLD = "#D4AF37";          // primary gold
const GOLD_LIGHT = "#EBC868";    // highlight
const GOLD_DEEP = "#9A7A1F";     // shadow gold
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

// ───── Dolphin SVG (game-icons via Iconify, verified elegant leaping silhouette) ─────
function Dolphin({
  size = 120,
  opacity = 1,
  gradient = true,
}: { size?: number; opacity?: number; gradient?: boolean }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 512 512" fill="none">
      <Defs>
        <SvgGradient id="dolphinGold" x1="0" y1="0" x2="1" y2="1">
          <Stop offset="0" stopColor={GOLD_LIGHT} stopOpacity={1} />
          <Stop offset="0.5" stopColor={GOLD} stopOpacity={1} />
          <Stop offset="1" stopColor={GOLD_DEEP} stopOpacity={1} />
        </SvgGradient>
      </Defs>
      <G opacity={opacity}>
        {/* Main dolphin body (leaping) */}
        <Path
          d="M123.22 47.23c29.498 15.152 55.025 36.05 55.53 67.366c-93.62 83.867-83.862 179.356-97.002 270.34c-67.68 55.552-67.57 90.948-60.9 101.227c3.94.743 29.11-25.94 48.326-30.397c14.23-4.094 12.284-15.99 16.273-25.275c2.438 14.55 7.17 22.612 17.133 25.485c12.874 3.36 44.932 28.15 51.53 25.504c1.374-20.382-26.01-63.854-48.028-90.087c41.012-63.28 81.365-136.458 211.162-207.77c-3.21-3.706-6.216-6.45-8.8-7.986l9.198-15.472c11.617 6.907 20.522 19.56 29.248 35.033c5.94 10.532 11.528 22.644 16.96 35.117c15.682-32.87 22.983-66.406 16.402-90.254l17.35-4.786a87 87 0 0 1 1.927 8.83c33.29-4.253 55.718-13.083 85.11-29.322c3.744-2.068 19.054-13.012-.117-16.03c12.62-9.017 7.54-12.063 1.973-15.152c-6.486-3.6-20.302-8.948-35.758-8.556c-12.124-27.863-39.63-47.772-82.225-47.696c-28.532.052-63.842 9.086-105.828 30.688C217.895 27.64 164.92 20.468 123.22 47.23"
          fill={gradient ? "url(#dolphinGold)" : GOLD}
        />
        {/* Eye */}
        <Path
          d="M410.162 75.97a9 9 0 1 1 0 18a9 9 0 0 1 0-18"
          fill={gradient ? INK : INK}
          opacity={gradient ? 1 : 0.5}
        />
      </G>
    </Svg>
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
      {/* ╔══════════════ FRONT ══════════════╗ */}
      <Animated.View
        pointerEvents={flipped ? "none" : "auto"}
        style={[
          styles.cardAbs,
          { transform: [{ perspective: 1200 }, { rotateY: frontRotate }], opacity: frontOpacity },
        ]}
      >
        <View style={styles.cardInner}>
          {/* Outer hairline gold frame */}
          <View pointerEvents="none" style={styles.outerHairline} />
          {/* Inner hairline (a touch in) */}
          <View pointerEvents="none" style={styles.innerHairline} />

          {/* Corner ornaments */}
          <CornerOrn position="tl" />
          <CornerOrn position="tr" />
          <CornerOrn position="bl" />
          <CornerOrn position="br" />

          {/* ─── Top row: brand wordmark (RTL: brand right, status left) ─── */}
          <View style={styles.topRow}>
            <View style={styles.brandRight}>
              <Text style={styles.brandTitleHe}>תושב אילת</Text>
              <View style={styles.brandLine} />
              <Text style={styles.brandSub}>EILAT RESIDENT · VIP</Text>
            </View>

            <View style={styles.statusBox}>
              <View style={styles.statusDot} />
              <Text style={styles.statusText}>MEMBER</Text>
            </View>
          </View>

          {/* ─── Hero: bold dolphin ─── */}
          <View style={styles.heroWrap} pointerEvents="none">
            <Dolphin size={160} opacity={1} gradient />
          </View>

          {/* ─── Center-left VIP plate ─── */}
          <View style={styles.vipPlateWrap} pointerEvents="none">
            <View style={styles.vipPlate}>
              <Text style={styles.vipPlateText}>VIP</Text>
            </View>
          </View>

          {/* ─── Bottom divider line ─── */}
          <View style={styles.divider} pointerEvents="none" />

          {/* ─── Bottom row: tap hint + app url ─── */}
          <View style={styles.bottomRow}>
            <Text style={styles.flipHint}>{interactive ? "↻ לחצו להפיכת הכרטיס" : ""}</Text>
            <Text style={styles.appUrl}>EILATUSH.APP</Text>
          </View>
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
          {/* Same hairline frame */}
          <View pointerEvents="none" style={styles.outerHairline} />
          <View pointerEvents="none" style={styles.innerHairline} />

          <CornerOrn position="tl" />
          <CornerOrn position="tr" />
          <CornerOrn position="bl" />
          <CornerOrn position="br" />

          {/* Dolphin watermark (very subtle) — center */}
          <View pointerEvents="none" style={styles.watermarkWrap}>
            <Dolphin size={180} opacity={0.04} gradient={false} />
          </View>

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

          {/* Details grid */}
          <View style={styles.detailsGrid}>
            <Detail label="תאריך לידה" value={displayDob} />
            <Detail label="תקף עד" value={displayExpiry} highlight />
            <Detail label="סטטוס" value="פעיל" highlight />
            <Detail label="חברות" value="6 חודשים" />
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
  watermarkWrap: {
    position: "absolute",
    top: "50%",
    left: 0,
    right: 0,
    alignItems: "center",
    transform: [{ translateY: -90 }],
  },
  backHeader: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 2,
  },
  backTitle: {
    color: GOLD,
    fontSize: 13,
    fontWeight: "900",
    letterSpacing: 2.4,
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
    alignItems: "flex-end",
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
