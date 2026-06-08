'use client';

import React, { useEffect, useRef, useState } from "react";
import { View, Text, StyleSheet, Pressable, Image, Animated, Platform, Easing } from "react-native";
import { LinearGradient } from "expo-linear-gradient";

const MASCOT_IMG = require("../assets/images/eilatush-mascot.png");

const GOLD = "#D4AF37";
const GOLD_LIGHT = "#F2D785";
const GOLD_DARK = "#A57C1B";
const INK_2 = "#1A1A1A";

type Props = {
  fullName?: string;
  memberNumber?: string;
  dob?: string; // YYYY-MM-DD
  expiryDate?: string; // YYYY-MM-DD
  // "preview" hides personal details and shows generic copy for the logged-out preview
  preview?: boolean;
  // when true, card is interactive and tap flips between front/back
  interactive?: boolean;
};

function formatHebDate(iso?: string): string {
  if (!iso) return "";
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
      duration: 550,
      easing: Easing.inOut(Easing.cubic),
      // Web doesn't fully support useNativeDriver for transform rotateY,
      // so we keep it off for cross-platform parity.
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

  return (
    <Pressable onPress={handlePress} style={styles.wrap} accessibilityLabel="כרטיס VIP — לחץ להפיכה">
      {/* FRONT */}
      <Animated.View
        pointerEvents={flipped ? "none" : "auto"}
        style={[
          styles.cardAbs,
          { transform: [{ perspective: 1000 }, { rotateY: frontRotate }], opacity: frontOpacity },
        ]}
      >
        <LinearGradient
          colors={["#000", INK_2, "#000"]}
          start={{ x: 0, y: 0 }}
          end={{ x: 1, y: 1 }}
          style={styles.card}
        >
          {/* Decorative gold lines */}
          <View pointerEvents="none" style={[styles.line, styles.lineTopRight]} />
          <View pointerEvents="none" style={[styles.line, styles.lineMidRight]} />
          <View pointerEvents="none" style={[styles.line, styles.lineBotLeft]} />
          <View pointerEvents="none" style={[styles.line, styles.lineMidLeft]} />
          <View pointerEvents="none" style={styles.cornerTL} />
          <View pointerEvents="none" style={styles.cornerBR} />

          {/* Top label */}
          <View style={styles.topRow}>
            <Text style={styles.brandSmall} numberOfLines={1}>אילתוש · EILATUSH</Text>
            <Text style={styles.chipText}>VIP</Text>
          </View>

          {/* Mascot watermark (gold-tinted) */}
          <View style={styles.mascotWrap} pointerEvents="none">
            <Image
              source={MASCOT_IMG}
              style={styles.mascot}
              resizeMode="contain"
            />
          </View>

          {/* Big title */}
          <View style={styles.titleBlock}>
            <Text style={styles.bigTitle}>תושב אילת</Text>
            <Text style={styles.bigTitleGold}>VIP</Text>
          </View>

          {/* Bottom hint */}
          <View style={styles.bottomRow}>
            <Text style={styles.tapHint}>{interactive ? "לחצו לפרטים ↻" : "כרטיס דיגיטלי"}</Text>
            <Text style={styles.brandTiny}>EILATUSH.APP</Text>
          </View>
        </LinearGradient>
      </Animated.View>

      {/* BACK */}
      <Animated.View
        pointerEvents={flipped ? "auto" : "none"}
        style={[
          styles.cardAbs,
          { transform: [{ perspective: 1000 }, { rotateY: backRotate }], opacity: backOpacity },
        ]}
      >
        <LinearGradient
          colors={[INK_2, "#000", INK_2]}
          start={{ x: 0, y: 0 }}
          end={{ x: 0, y: 1 }}
          style={styles.card}
        >
          <View pointerEvents="none" style={[styles.line, styles.lineTopRight]} />
          <View pointerEvents="none" style={[styles.line, styles.lineBotLeft]} />
          <View pointerEvents="none" style={styles.cornerTL} />
          <View pointerEvents="none" style={styles.cornerBR} />

          <View style={styles.topRow}>
            <Text style={styles.brandSmall} numberOfLines={1}>תושב אילת · VIP</Text>
            <Text style={styles.chipText}>{preview ? "DEMO" : memberNumber || ""}</Text>
          </View>

          <View style={styles.detailsBlock}>
            <Text style={styles.fieldLabel}>שם מלא</Text>
            <Text style={styles.fieldValue} numberOfLines={1}>{preview ? "שמכם יופיע כאן" : fullName || "—"}</Text>

            <View style={styles.row2}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>תאריך לידה</Text>
                <Text style={styles.fieldValueSm}>{preview ? "—" : formatHebDate(dob)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>מס׳ חבר</Text>
                <Text style={styles.fieldValueSm}>{preview ? "VIP-2026-0000" : memberNumber || "—"}</Text>
              </View>
            </View>

            <View style={styles.row2}>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>תקף עד</Text>
                <Text style={styles.fieldValueSm}>{preview ? "6 חודשים מההרשמה" : formatHebDate(expiryDate)}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.fieldLabel}>סטטוס</Text>
                <Text style={[styles.fieldValueSm, { color: "#33D17A" }]}>פעיל</Text>
              </View>
            </View>
          </View>

          <View style={styles.bottomRow}>
            <Text style={styles.tapHint}>↻ חזרה לחזית</Text>
            <Text style={styles.brandTiny}>EILATUSH.APP</Text>
          </View>
        </LinearGradient>
      </Animated.View>
    </Pressable>
  );
}

const CARD_RADIUS = 22;

const styles = StyleSheet.create({
  wrap: {
    width: "100%",
    maxWidth: 380,
    aspectRatio: 1.586, // ISO/IEC 7810 ID-1 (credit card)
    alignSelf: "center",
  },
  cardAbs: {
    position: "absolute",
    inset: 0 as any,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backfaceVisibility: "hidden" as any,
  },
  card: {
    flex: 1,
    borderRadius: CARD_RADIUS,
    padding: 18,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: GOLD_DARK,
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOpacity: 0.35,
        shadowRadius: 18,
        shadowOffset: { width: 0, height: 10 },
      },
      android: { elevation: 10 },
      default: {
        // @ts-ignore — web only
        boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
      },
    }),
  },
  topRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    zIndex: 2,
  },
  brandSmall: {
    color: GOLD,
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 1.2,
    textAlign: "right",
  },
  brandTiny: {
    color: GOLD,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1.5,
    opacity: 0.7,
  },
  chipText: {
    color: "#000",
    fontSize: 11,
    fontWeight: "900",
    letterSpacing: 1.5,
    backgroundColor: GOLD,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    overflow: "hidden" as any,
  },
  mascotWrap: {
    position: "absolute",
    bottom: -10,
    left: -10,
    opacity: 0.18,
    transform: [{ rotate: "-8deg" }],
  },
  mascot: {
    width: 200,
    height: 200,
    // @ts-ignore — RN supports tintColor on Image
    tintColor: GOLD,
  },
  titleBlock: {
    position: "absolute",
    right: 18,
    bottom: 56,
    alignItems: "flex-end",
  },
  bigTitle: {
    color: "#FFF",
    fontSize: 26,
    fontWeight: "900",
    letterSpacing: 0.5,
  },
  bigTitleGold: {
    color: GOLD_LIGHT,
    fontSize: 44,
    fontWeight: "900",
    letterSpacing: 2,
    lineHeight: 46,
  },
  bottomRow: {
    position: "absolute",
    left: 18,
    right: 18,
    bottom: 14,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
  },
  tapHint: {
    color: GOLD,
    fontSize: 11,
    opacity: 0.75,
    fontWeight: "600",
  },
  detailsBlock: {
    marginTop: 16,
    gap: 10,
  },
  fieldLabel: {
    color: GOLD,
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 0.8,
    textAlign: "right",
    opacity: 0.75,
  },
  fieldValue: {
    color: "#FFF",
    fontSize: 20,
    fontWeight: "800",
    textAlign: "right",
    marginTop: 2,
  },
  fieldValueSm: {
    color: "#FFF",
    fontSize: 14,
    fontWeight: "700",
    textAlign: "right",
    marginTop: 2,
  },
  row2: {
    flexDirection: "row-reverse",
    gap: 14,
    marginTop: 8,
  },
  // Decorative gold lines (clipped by overflow:hidden of card)
  line: {
    position: "absolute",
    backgroundColor: GOLD,
    opacity: 0.45,
  },
  lineTopRight: {
    top: 30,
    right: -20,
    width: 120,
    height: 1.2,
    transform: [{ rotate: "35deg" }],
  },
  lineMidRight: {
    top: 60,
    right: -30,
    width: 90,
    height: 1,
    transform: [{ rotate: "35deg" }],
    opacity: 0.25,
  },
  lineBotLeft: {
    bottom: 40,
    left: -30,
    width: 140,
    height: 1.2,
    transform: [{ rotate: "35deg" }],
  },
  lineMidLeft: {
    bottom: 80,
    left: -20,
    width: 80,
    height: 1,
    transform: [{ rotate: "35deg" }],
    opacity: 0.25,
  },
  cornerTL: {
    position: "absolute",
    top: 10,
    left: 10,
    width: 24,
    height: 24,
    borderTopWidth: 2,
    borderLeftWidth: 2,
    borderColor: GOLD,
    opacity: 0.7,
    borderTopLeftRadius: 6,
  },
  cornerBR: {
    position: "absolute",
    bottom: 36,
    right: 10,
    width: 24,
    height: 24,
    borderBottomWidth: 2,
    borderRightWidth: 2,
    borderColor: GOLD,
    opacity: 0.7,
    borderBottomRightRadius: 6,
  },
});
