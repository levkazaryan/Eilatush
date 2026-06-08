'use client';

import React from "react";
import { View, Text, StyleSheet, Image, Pressable, Platform } from "react-native";
import { COLORS, RADIUS } from "../theme";
import type { VIPDiscount } from "../api";

const PLACEHOLDER_BY_BIZ: Record<string, string> = {
  // fallback emojis for businesses without an image
  "Cafe Wifi": "🍋",
  "US Crispy Chicken": "🍗",
  "OPATRA London": "💎",
};

export default function DiscountCard({ item }: { item: VIPDiscount }) {
  const hasImg = !!item.image_url;
  const emoji = PLACEHOLDER_BY_BIZ[item.business_name] || "🎁";

  return (
    <View style={styles.card}>
      <View style={styles.imgWrap}>
        {hasImg ? (
          <Image source={{ uri: item.image_url! }} style={styles.img} resizeMode="cover" />
        ) : (
          <View style={styles.imgFallback}>
            <Text style={styles.imgFallbackEmoji}>{emoji}</Text>
          </View>
        )}
        <View style={styles.freeBadge}>
          <Text style={styles.freeBadgeText}>חינם</Text>
        </View>
        {item.age_restriction ? (
          <View style={styles.ageBadge}>
            <Text style={styles.ageBadgeText}>{item.age_restriction}</Text>
          </View>
        ) : null}
      </View>
      <View style={styles.body}>
        <Text style={styles.business} numberOfLines={1}>{item.business_name}</Text>
        <Text style={styles.gift} numberOfLines={3}>{item.gift_text}</Text>
        <View style={styles.metaRow}>
          <Text style={styles.metaPlace}>📍 {item.place}</Text>
          {item.category ? <Text style={styles.metaCat}>· {item.category}</Text> : null}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.card,
    borderRadius: RADIUS.lg,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: COLORS.border,
    marginBottom: 12,
    ...Platform.select({
      ios: { shadowColor: "#0F172A", shadowOpacity: 0.06, shadowRadius: 10, shadowOffset: { width: 0, height: 3 } },
      android: { elevation: 2 },
      default: { boxShadow: "0 3px 10px rgba(15,23,42,0.06)" } as any,
    }),
  },
  imgWrap: {
    width: "100%",
    aspectRatio: 16 / 9,
    backgroundColor: "#EFEFEF",
    position: "relative",
  },
  img: { width: "100%", height: "100%" },
  imgFallback: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#F8F0E3",
  },
  imgFallbackEmoji: { fontSize: 72 },
  freeBadge: {
    position: "absolute",
    top: 10,
    insetInlineStart: 10,
    backgroundColor: "#E63946",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  freeBadgeText: { color: "#fff", fontWeight: "900", fontSize: 12, letterSpacing: 0.5 },
  ageBadge: {
    position: "absolute",
    top: 10,
    insetInlineEnd: 10,
    backgroundColor: "rgba(0,0,0,0.7)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  ageBadgeText: { color: "#fff", fontWeight: "800", fontSize: 11 },
  body: { padding: 14 },
  business: {
    fontSize: 16,
    fontWeight: "900",
    color: COLORS.textPrimary,
    textAlign: "right",
    writingDirection: "rtl",
  },
  gift: {
    fontSize: 14,
    color: COLORS.textSecondary,
    marginTop: 4,
    textAlign: "right",
    writingDirection: "rtl",
    lineHeight: 20,
  },
  metaRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 6,
    marginTop: 8,
  },
  metaPlace: { color: COLORS.textMuted, fontSize: 12, fontWeight: "700" },
  metaCat: { color: COLORS.textMuted, fontSize: 12 },
});
