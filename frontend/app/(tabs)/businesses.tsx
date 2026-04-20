'use client';

import React, { useCallback, useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  RefreshControl,
  ActivityIndicator,
  Modal,
  Pressable,
  FlatList,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { api } from "../../api";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { BusinessCard, BusinessT, EmptyState } from "../../components";

type BizCategory = { slug: string; label: string; emoji: string; count: number };
type BizType = "business" | "professional";

export default function BusinessesScreen() {
  const router = useRouter();

  const [type, setType] = useState<BizType>("business");
  const [list, setList] = useState<BusinessT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [categoriesBiz, setCategoriesBiz] = useState<BizCategory[]>([]);
  const [categoriesPro, setCategoriesPro] = useState<BizCategory[]>([]);
  const [category, setCategory] = useState<string[]>([]);   // multi
  const [openNow, setOpenNow] = useState(false);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  const [filterOpen, setFilterOpen] = useState(false);

  const categories = type === "business" ? categoriesBiz : categoriesPro;

  const loadMeta = useCallback(async () => {
    try {
      const [catsBiz, catsPro] = await Promise.all([
        api.businessesCategories("business"),
        api.businessesCategories("professional"),
      ]);
      setCategoriesBiz(Array.isArray(catsBiz) ? catsBiz : []);
      setCategoriesPro(Array.isArray(catsPro) ? catsPro : []);
    } catch (e) {
      console.warn("loadMeta biz", e);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const data = await api.businesses({
        type,
        category: category.length ? category : undefined,
        open_now: type === "business" ? openNow : undefined,
        q: debouncedQuery || undefined,
        limit: 2000,
      });
      setList(Array.isArray(data) ? data : []);
    } catch (e) {
      console.warn("load biz", e);
      setList([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [type, JSON.stringify(category), openNow, debouncedQuery]);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  // Debounce search typing so we don't hit the API on every keystroke
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(t);
  }, [query]);

  const onRefresh = () => {
    setRefreshing(true);
    loadMeta();
    load();
  };

  const toggleCat = (slug: string) => {
    setCategory((arr) =>
      arr.includes(slug) ? arr.filter((v) => v !== slug) : [...arr, slug],
    );
  };

  const switchType = (t: BizType) => {
    if (t === type) return;
    setType(t);
    setCategory([]);     // reset category when switching (different taxonomy)
    setOpenNow(false);
  };

  const activeCount =
    category.length + (openNow ? 1 : 0) + (debouncedQuery ? 1 : 0);

  const categoryLabel =
    category.length === 0
      ? "כל הקטגוריות"
      : category.length === 1
        ? (() => {
            const c = categories.find((c) => c.slug === category[0]);
            return c ? `${c.emoji} ${c.label}` : category[0];
          })()
        : `${category.length} קטגוריות`;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>
          {type === "business" ? "עסקים באילת" : "אנשי מקצוע"}
        </Text>
        <Text style={styles.screenSub}>
          {list.length > 0
            ? `${list.length} ${type === "business" ? "עסקים" : "בעלי מקצוע"}`
            : type === "business"
              ? "כל העסקים באילת במקום אחד"
              : "בעלי מקצוע מומלצים באילת"}
        </Text>
      </View>

      {/* Top segmented toggle */}
      <View style={styles.segment}>
        <Pressable
          onPress={() => switchType("professional")}
          style={[styles.segmentItem, type === "professional" && styles.segmentItemActive]}
          testID="biz-toggle-professionals"
        >
          <Ionicons
            name="construct"
            size={16}
            color={type === "professional" ? "#fff" : COLORS.textSecondary}
          />
          <Text style={[styles.segmentText, type === "professional" && styles.segmentTextActive]}>
            אנשי מקצוע
          </Text>
        </Pressable>
        <Pressable
          onPress={() => switchType("business")}
          style={[styles.segmentItem, type === "business" && styles.segmentItemActive]}
          testID="biz-toggle-businesses"
        >
          <Ionicons
            name="storefront"
            size={16}
            color={type === "business" ? "#fff" : COLORS.textSecondary}
          />
          <Text style={[styles.segmentText, type === "business" && styles.segmentTextActive]}>
            עסקים
          </Text>
        </Pressable>
      </View>

      {/* Search box */}
      <View style={styles.searchBox}>
        <Ionicons name="search" size={18} color={COLORS.textMuted} />
        <TextInput
          placeholder={
            type === "business"
              ? "חיפוש שם עסק, תיאור, כתובת..."
              : "חיפוש שם או מקצוע..."
          }
          placeholderTextColor={COLORS.textMuted}
          style={styles.searchInput}
          value={query}
          onChangeText={setQuery}
          returnKeyType="search"
          testID="biz-search-input"
        />
        {query.length > 0 ? (
          <Pressable onPress={() => setQuery("")} hitSlop={8}>
            <Ionicons name="close-circle" size={18} color={COLORS.textMuted} />
          </Pressable>
        ) : null}
      </View>

      {/* Filter row */}
      <View style={styles.filterRow}>
        <Pressable
          onPress={() => setFilterOpen(true)}
          style={[
            styles.dropdownBtn,
            category.length > 0 && styles.dropdownBtnActive,
          ]}
          testID="biz-filter-cats"
        >
          <Ionicons
            name="pricetags-outline"
            size={14}
            color={category.length > 0 ? COLORS.primary : COLORS.textSecondary}
          />
          <Text
            style={[
              styles.dropdownBtnText,
              category.length > 0 && { color: COLORS.primary },
            ]}
            numberOfLines={1}
          >
            {categoryLabel}
          </Text>
          {category.length > 1 ? (
            <View style={styles.dropdownBadge}>
              <Text style={styles.dropdownBadgeText}>{category.length}</Text>
            </View>
          ) : null}
          <Ionicons
            name="chevron-down"
            size={12}
            color={category.length > 0 ? COLORS.primary : COLORS.textMuted}
          />
        </Pressable>

        {type === "business" ? (
          <Pressable
            onPress={() => setOpenNow((v) => !v)}
            style={[styles.dropdownBtn, openNow && styles.dropdownBtnActive]}
            testID="biz-chip-open-now"
          >
            <Ionicons
              name="time-outline"
              size={14}
              color={openNow ? COLORS.primary : COLORS.textSecondary}
            />
            <Text
              style={[
                styles.dropdownBtnText,
                openNow && { color: COLORS.primary },
              ]}
              numberOfLines={1}
            >
              {openNow ? "✓ פתוחים עכשיו" : "פתוחים עכשיו"}
            </Text>
          </Pressable>
        ) : null}

        {activeCount > 0 ? (
          <Pressable
            onPress={() => {
              setCategory([]);
              setOpenNow(false);
              setQuery("");
            }}
            style={styles.clearBtn}
          >
            <Ionicons name="close-circle" size={14} color={COLORS.primary} />
            <Text style={styles.clearBtnText}>נקה ({activeCount})</Text>
          </Pressable>
        ) : null}
      </View>

      <FlatList
        data={loading ? [] : list}
        keyExtractor={(item) => item.id}
        contentContainerStyle={{ paddingTop: SPACING.sm, paddingBottom: 120 }}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={COLORS.primary}
          />
        }
        initialNumToRender={12}
        windowSize={7}
        maxToRenderPerBatch={8}
        removeClippedSubviews
        renderItem={({ item }) => (
          <BusinessCard
            item={item}
            onPress={() => router.push(`/business/${item.id}`)}
          />
        )}
        ListEmptyComponent={
          loading ? (
            <View style={{ paddingVertical: 40 }}>
              <ActivityIndicator color={COLORS.primary} />
            </View>
          ) : (
            <EmptyState
              title={
                type === "business"
                  ? "לא נמצאו עסקים מתאימים"
                  : "לא נמצאו בעלי מקצוע"
              }
              subtitle="נסו לשנות או לאפס את הסינון"
              icon={type === "business" ? "storefront-outline" : "construct-outline"}
            />
          )
        }
      />

      {/* Categories bottom sheet */}
      <Modal
        visible={filterOpen}
        transparent
        animationType="slide"
        onRequestClose={() => setFilterOpen(false)}
      >
        <Pressable style={styles.backdrop} onPress={() => setFilterOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={styles.sheetHandle} />
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>🏷️ בחר/י קטגוריות</Text>
              <View style={{ flexDirection: "row-reverse", gap: 10, alignItems: "center" }}>
                {category.length > 0 ? (
                  <Pressable onPress={() => setCategory([])} hitSlop={8}>
                    <Text style={styles.sheetClearText}>נקה</Text>
                  </Pressable>
                ) : null}
                <Pressable onPress={() => setFilterOpen(false)} hitSlop={10}>
                  <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                </Pressable>
              </View>
            </View>
            <Text style={styles.sheetSub}>אפשר לבחור כמה אפשרויות</Text>
            <ScrollView contentContainerStyle={{ paddingBottom: 20 }}>
              {categories
                .filter((c) => c.slug !== "all")
                .sort((a, b) => b.count - a.count)
                .map((c) => {
                  const selected = category.includes(c.slug);
                  return (
                    <Pressable
                      key={c.slug}
                      onPress={() => toggleCat(c.slug)}
                      style={[
                        styles.optionRow,
                        selected && styles.optionRowSelected,
                      ]}
                    >
                      <Ionicons
                        name={selected ? "checkbox" : "square-outline"}
                        size={22}
                        color={selected ? COLORS.primary : COLORS.textMuted}
                      />
                      <Text
                        style={[
                          styles.optionLabel,
                          selected && { color: COLORS.primary, fontWeight: "900" },
                        ]}
                      >
                        {c.emoji} {c.label}
                      </Text>
                      {c.count > 0 ? (
                        <Text style={styles.optionCount}>{c.count}</Text>
                      ) : null}
                    </Pressable>
                  );
                })}
            </ScrollView>
            <Pressable
              onPress={() => setFilterOpen(false)}
              style={({ pressed }) => [
                styles.applyBtn,
                pressed && { opacity: 0.85 },
              ]}
            >
              <Text style={styles.applyBtnText}>
                הצג {list.length} {type === "business" ? "עסקים" : "בעלי מקצוע"}
              </Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    paddingHorizontal: SPACING.md,
    paddingTop: SPACING.md,
    paddingBottom: SPACING.xs,
  },
  screenTitle: {
    color: COLORS.textPrimary,
    fontSize: 28,
    fontWeight: "900",
    textAlign: "right",
    writingDirection: "rtl",
  },
  screenSub: {
    color: COLORS.textMuted,
    fontSize: 13,
    marginTop: 4,
    textAlign: "right",
  },

  // Segmented toggle
  segment: {
    flexDirection: "row-reverse",
    marginHorizontal: SPACING.md,
    marginTop: SPACING.md,
    backgroundColor: COLORS.card,
    borderRadius: RADIUS.pill,
    padding: 4,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  segmentItem: {
    flex: 1,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 10,
    gap: 6,
    borderRadius: RADIUS.pill,
  },
  segmentItemActive: {
    backgroundColor: COLORS.primary,
  },
  segmentText: {
    color: COLORS.textSecondary,
    fontSize: 14,
    fontWeight: "800",
  },
  segmentTextActive: {
    color: "#fff",
  },

  // Search box
  searchBox: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: COLORS.card,
    marginHorizontal: SPACING.md,
    marginTop: SPACING.md,
    paddingHorizontal: 14,
    height: 44,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    gap: 8,
  },
  searchInput: {
    flex: 1,
    color: COLORS.textPrimary,
    fontSize: 14,
    textAlign: "right",
    writingDirection: "rtl",
    height: "100%",
    ...({ outlineStyle: "none" } as any),
  },

  // Filter row
  filterRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "flex-end",
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.md,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    flexWrap: "wrap",
  },
  dropdownBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: RADIUS.pill,
    backgroundColor: "#fff",
    borderWidth: 1,
    borderColor: COLORS.border,
    gap: 6,
    maxWidth: 220,
  },
  dropdownBtnActive: {
    backgroundColor: "rgba(230,57,70,0.08)",
    borderColor: "rgba(230,57,70,0.40)",
  },
  dropdownBtnText: {
    color: COLORS.textSecondary,
    fontSize: 12,
    fontWeight: "700",
    maxWidth: 160,
  },
  dropdownBadge: {
    backgroundColor: COLORS.primary,
    borderRadius: 10,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 5,
    alignItems: "center",
    justifyContent: "center",
  },
  dropdownBadgeText: { color: "#fff", fontSize: 10, fontWeight: "900" },
  clearBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(230,57,70,0.12)",
    borderWidth: 1,
    borderColor: COLORS.primary,
  },
  clearBtnText: { color: COLORS.primary, fontSize: 12, fontWeight: "800" },

  // Modal
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(15,23,42,0.45)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: COLORS.card,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    maxHeight: "75%",
    paddingTop: 10,
    paddingHorizontal: SPACING.md,
  },
  sheetHandle: {
    alignSelf: "center",
    width: 44,
    height: 5,
    borderRadius: 3,
    backgroundColor: COLORS.border,
    marginBottom: 8,
  },
  sheetHeader: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    marginBottom: 6,
  },
  sheetTitle: {
    color: COLORS.textPrimary,
    fontSize: 17,
    fontWeight: "900",
    textAlign: "right",
    flex: 1,
  },
  sheetSub: {
    color: COLORS.textMuted,
    fontSize: 12,
    textAlign: "right",
    paddingHorizontal: 6,
    paddingBottom: 8,
  },
  sheetClearText: { color: COLORS.primary, fontSize: 13, fontWeight: "800" },
  optionRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 6,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(15,23,42,0.05)",
    gap: 10,
  },
  optionRowSelected: { backgroundColor: "rgba(230,57,70,0.06)" },
  optionLabel: {
    color: COLORS.textPrimary,
    fontSize: 15,
    fontWeight: "700",
    flex: 1,
    textAlign: "right",
  },
  optionCount: {
    color: COLORS.textMuted,
    fontSize: 12,
    fontWeight: "700",
    marginStart: 6,
  },
  applyBtn: {
    backgroundColor: COLORS.primary,
    paddingVertical: 14,
    marginBottom: 10,
    borderRadius: RADIUS.pill,
    alignItems: "center",
  },
  applyBtnText: { color: "#fff", fontWeight: "900", fontSize: 14 },
});
