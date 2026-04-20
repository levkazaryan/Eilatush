'use client';

import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Image,
  ActivityIndicator,
  TouchableOpacity,
  Pressable,
  Linking,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  api,
  openLink,
  openPhone,
  openWhatsApp,
  openEmail,
  openWaze,
  displayPhone,
} from "../../api";
import { BusinessT, BIZ_CATEGORY } from "../../components";
import { COLORS, RADIUS, SPACING } from "../../theme";

export default function BusinessDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [item, setItem] = useState<BusinessT | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const d = await api.business(String(id));
        setItem(d);
      } catch (e) {
        console.warn("load business", e);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  if (loading) {
    return (
      <SafeAreaView style={styles.root}>
        <View style={styles.centered}>
          <ActivityIndicator color={COLORS.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (!item) {
    return (
      <SafeAreaView style={styles.root}>
        <View style={styles.centered}>
          <Ionicons name="alert-circle-outline" size={48} color={COLORS.textMuted} />
          <Text style={styles.notFoundText}>לא נמצא</Text>
          <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
            <Text style={styles.backBtnText}>חזרה</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const isPro = item.type === "professional";
  const primaryTag = (item.tags || [])[0];
  const tagInfo = primaryTag ? BIZ_CATEGORY[primaryTag] : null;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      {/* header bar */}
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={10}>
          <Ionicons name="chevron-forward" size={26} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topBarTitle} numberOfLines={1}>
          {isPro ? "בעל מקצוע" : "עסק באילת"}
        </Text>
        <View style={{ width: 26 }} />
      </View>

      <ScrollView contentContainerStyle={{ paddingBottom: 140 }}>
        {/* Hero image or avatar */}
        {!isPro && item.image ? (
          <Image source={{ uri: item.image }} style={styles.hero} />
        ) : isPro && item.image ? (
          <Image source={{ uri: item.image }} style={styles.heroPro} resizeMode="contain" />
        ) : (
          <View
            style={[
              styles.hero,
              styles.heroPlaceholder,
              isPro && tagInfo ? { backgroundColor: tagInfo.color + "18" } : null,
            ]}
          >
            <Ionicons
              name={
                isPro
                  ? (tagInfo?.icon || "construct-outline")
                  : (tagInfo?.icon || "storefront-outline")
              }
              size={60}
              color={isPro && tagInfo ? tagInfo.color : COLORS.textMuted}
            />
          </View>
        )}

        <View style={styles.body}>
          {/* Name */}
          <Text style={styles.name}>{item.name}</Text>
          {item.subtitle ? <Text style={styles.subtitle}>{item.subtitle}</Text> : null}

          {/* Open-now indicator */}
          {item.open_hours ? (
            <View style={styles.openRow}>
              {item.open_now ? (
                <View style={[styles.openPill, { backgroundColor: "rgba(34,197,94,0.14)" }]}>
                  <View style={styles.openDotInner} />
                  <Text style={[styles.openPillText, { color: COLORS.success }]}>
                    פתוח עכשיו
                  </Text>
                </View>
              ) : (
                <View style={[styles.openPill, { backgroundColor: "rgba(239,68,68,0.12)" }]}>
                  <Text style={[styles.openPillText, { color: COLORS.danger }]}>
                    סגור עכשיו
                  </Text>
                </View>
              )}
              <Ionicons name="time-outline" size={14} color={COLORS.textMuted} />
              <Text style={styles.openHoursText}>{item.open_hours}</Text>
            </View>
          ) : null}

          {/* Category tags */}
          {(item.tags || []).length > 0 ? (
            <View style={styles.tagsRow}>
              {(item.tags || []).map((slug) => {
                const c = BIZ_CATEGORY[slug];
                return (
                  <View key={slug} style={styles.tagPill}>
                    <Text style={styles.tagPillText}>
                      {c ? `${c.emoji} ${c.label}` : slug}
                    </Text>
                  </View>
                );
              })}
            </View>
          ) : null}

          {/* Address */}
          {item.address ? (
            <Pressable
              style={styles.infoCard}
              onPress={() => openWaze(`${item.name} ${item.address}`)}
            >
              <Ionicons name="location" size={18} color={COLORS.primary} />
              <View style={{ flex: 1 }}>
                <Text style={styles.infoLabel}>כתובת</Text>
                <Text style={styles.infoValue}>{item.address}</Text>
              </View>
              <View style={styles.wazeMini}>
                <Ionicons name="navigate" size={14} color="#fff" />
                <Text style={styles.wazeMiniText}>Waze</Text>
              </View>
            </Pressable>
          ) : null}

          {/* Phone */}
          {item.phone ? (
            <Pressable style={styles.infoCard} onPress={() => openPhone(item.phone || undefined)}>
              <Ionicons name="call" size={18} color={COLORS.success} />
              <View style={{ flex: 1 }}>
                <Text style={styles.infoLabel}>טלפון</Text>
                <Text style={styles.infoValue}>{displayPhone(item.phone)}</Text>
              </View>
              <Ionicons name="chevron-back" size={18} color={COLORS.textMuted} />
            </Pressable>
          ) : null}

          {/* Email */}
          {item.email ? (
            <Pressable
              style={styles.infoCard}
              onPress={() => openEmail(item.email || undefined, `פנייה דרך אילתוש - ${item.name}`)}
            >
              <Ionicons name="mail" size={18} color={COLORS.accent} />
              <View style={{ flex: 1 }}>
                <Text style={styles.infoLabel}>אימייל</Text>
                <Text style={styles.infoValue}>{item.email}</Text>
              </View>
              <Ionicons name="chevron-back" size={18} color={COLORS.textMuted} />
            </Pressable>
          ) : null}

          {/* Website */}
          {item.website ? (
            <Pressable style={styles.infoCard} onPress={() => openLink(item.website || undefined)}>
              <Ionicons name="globe-outline" size={18} color={COLORS.primary} />
              <View style={{ flex: 1 }}>
                <Text style={styles.infoLabel}>אתר</Text>
                <Text style={styles.infoValue} numberOfLines={1}>
                  {item.website}
                </Text>
              </View>
              <Ionicons name="chevron-back" size={18} color={COLORS.textMuted} />
            </Pressable>
          ) : null}

          {/* Description */}
          {item.description ? (
            <View style={styles.section}>
              <Text style={styles.sectionTitle}>אודות</Text>
              <Text style={styles.description}>{item.description}</Text>
            </View>
          ) : null}

          {/* Source footer */}
          <View style={styles.sourceBox}>
            <Text style={styles.sourceText}>מקור: {item.source_name || item.source}</Text>
            {item.source_url ? (
              <Pressable onPress={() => openLink(item.source_url || undefined)}>
                <Text style={styles.sourceLinkText}>פתח במקור ↗</Text>
              </Pressable>
            ) : null}
          </View>
        </View>
      </ScrollView>

      {/* Sticky bottom action bar */}
      {(item.phone || item.whatsapp) ? (
        <View style={styles.stickyBar}>
          {item.whatsapp ? (
            <TouchableOpacity
              style={[styles.stickyBtn, { backgroundColor: COLORS.whatsapp }]}
              onPress={() =>
                openWhatsApp(
                  item.whatsapp || undefined,
                  `היי, מצאתי אותך באילתוש ואשמח לקבל פרטים על ${item.name}`,
                )
              }
            >
              <Ionicons name="logo-whatsapp" size={18} color="#fff" />
              <Text style={styles.stickyBtnText}>WhatsApp</Text>
            </TouchableOpacity>
          ) : null}
          {item.phone ? (
            <TouchableOpacity
              style={[styles.stickyBtn, { backgroundColor: COLORS.success }]}
              onPress={() => openPhone(item.phone || undefined)}
            >
              <Ionicons name="call" size={18} color="#fff" />
              <Text style={styles.stickyBtnText}>חייג/י</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", padding: SPACING.md },
  notFoundText: { color: COLORS.textMuted, fontSize: 15, marginTop: 10 },
  backBtn: {
    marginTop: 20,
    backgroundColor: COLORS.primary,
    paddingVertical: 12,
    paddingHorizontal: 26,
    borderRadius: RADIUS.pill,
  },
  backBtnText: { color: "#fff", fontWeight: "900" },

  topBar: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.sm,
    backgroundColor: COLORS.card,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  topBarTitle: {
    color: COLORS.textPrimary,
    fontSize: 16,
    fontWeight: "900",
    textAlign: "center",
    flex: 1,
  },

  hero: { width: "100%", height: 220, backgroundColor: "#F1F5F9" },
  heroPro: {
    width: "100%",
    height: 280,
    backgroundColor: "#F1F5F9",
  },
  heroPlaceholder: { alignItems: "center", justifyContent: "center" },

  body: { padding: SPACING.md },
  name: {
    color: COLORS.textPrimary,
    fontSize: 26,
    fontWeight: "900",
    textAlign: "right",
    writingDirection: "rtl",
  },
  subtitle: {
    color: COLORS.textSecondary,
    fontSize: 15,
    fontWeight: "600",
    marginTop: 4,
    textAlign: "right",
    writingDirection: "rtl",
  },

  openRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 8,
    marginTop: 10,
  },
  openPill: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: RADIUS.pill,
  },
  openDotInner: { width: 6, height: 6, borderRadius: 3, backgroundColor: COLORS.success },
  openPillText: { fontSize: 12, fontWeight: "800" },
  openHoursText: { color: COLORS.textMuted, fontSize: 12, flex: 1, textAlign: "right" },

  tagsRow: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 12,
  },
  tagPill: {
    backgroundColor: "rgba(230,57,70,0.08)",
    borderWidth: 1,
    borderColor: "rgba(230,57,70,0.25)",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: RADIUS.pill,
  },
  tagPillText: {
    color: COLORS.primary,
    fontSize: 12,
    fontWeight: "800",
  },

  infoCard: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.md,
    paddingHorizontal: 12,
    paddingVertical: 12,
    gap: 10,
    marginTop: 10,
  },
  infoLabel: { color: COLORS.textMuted, fontSize: 11, fontWeight: "700", textAlign: "right" },
  infoValue: {
    color: COLORS.textPrimary,
    fontSize: 14,
    fontWeight: "700",
    marginTop: 2,
    textAlign: "right",
    writingDirection: "rtl",
  },
  wazeMini: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    backgroundColor: "#3DAEFF",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: RADIUS.pill,
  },
  wazeMiniText: { color: "#fff", fontSize: 12, fontWeight: "900" },

  section: { marginTop: 18 },
  sectionTitle: {
    color: COLORS.textPrimary,
    fontSize: 15,
    fontWeight: "900",
    textAlign: "right",
    marginBottom: 6,
  },
  description: {
    color: COLORS.textSecondary,
    fontSize: 14,
    lineHeight: 22,
    textAlign: "right",
    writingDirection: "rtl",
  },

  sourceBox: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 24,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  sourceText: { color: COLORS.textMuted, fontSize: 11 },
  sourceLinkText: { color: COLORS.primary, fontSize: 12, fontWeight: "800" },

  stickyBar: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    flexDirection: "row-reverse",
    padding: SPACING.md,
    gap: 10,
    backgroundColor: COLORS.card,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  stickyBtn: {
    flex: 1,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 14,
    borderRadius: RADIUS.pill,
  },
  stickyBtnText: { color: "#fff", fontWeight: "900", fontSize: 15 },
});
