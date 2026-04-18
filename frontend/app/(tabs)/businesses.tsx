import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../api";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { BusinessCard, BusinessT, FilterChip, EmptyState } from "../../components";

const CATEGORIES: { key: string; label: string }[] = [
  { key: "", label: "הכל" },
  { key: "restaurant", label: "מסעדות" },
  { key: "bar", label: "ברים" },
  { key: "cafe", label: "בתי קפה" },
  { key: "shop", label: "חנויות" },
  { key: "service", label: "שירותים" },
  { key: "beauty", label: "יופי" },
  { key: "sport", label: "ספורט" },
];

export default function BusinessesScreen() {
  const [list, setList] = useState<BusinessT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [category, setCategory] = useState("");
  const [openOnly, setOpenOnly] = useState(false);
  const [query, setQuery] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api.businesses({
        category: category || undefined,
        open_now: openOnly,
        q: query || undefined,
      });
      setList(Array.isArray(data) ? data : []);
    } catch (e) {
      console.warn("load biz", e);
      setList([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [category, openOnly, query]);

  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => load(), 250);
    return () => clearTimeout(t);
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const openNowCount = useMemo(() => list.filter((b) => b.open_now).length, [list]);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>עסקים באילת</Text>
        <Text style={styles.screenSub}>
          {openOnly ? `${list.length} עסקים פתוחים עכשיו` : `${list.length} עסקים · ${openNowCount} פתוחים עכשיו`}
        </Text>
      </View>

      <View style={styles.searchBox}>
        <Ionicons name="search" size={18} color={COLORS.textMuted} />
        <TextInput
          placeholder="חיפוש לפי שם, תגית, תיאור..."
          placeholderTextColor={COLORS.textMuted}
          style={styles.searchInput}
          value={query}
          onChangeText={setQuery}
          testID="biz-search-input"
        />
      </View>

      <View style={styles.chipsRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: SPACING.md, flexDirection: "row-reverse" }}>
          <FilterChip
            label={openOnly ? "✓ פתוחים עכשיו" : "פתוחים עכשיו"}
            active={openOnly}
            onPress={() => setOpenOnly((s) => !s)}
            testID="biz-chip-open-now"
          />
          {CATEGORIES.map((c) => (
            <FilterChip
              key={c.key || "all"}
              label={c.label}
              active={category === c.key}
              onPress={() => setCategory(c.key)}
              testID={`biz-chip-${c.key || "all"}`}
            />
          ))}
        </ScrollView>
      </View>

      <ScrollView
        contentContainerStyle={{ paddingTop: SPACING.sm, paddingBottom: 120 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />}
      >
        {loading ? (
          <View style={{ paddingVertical: 40 }}>
            <ActivityIndicator color={COLORS.primary} />
          </View>
        ) : list.length === 0 ? (
          <EmptyState title="אין עסקים תואמים" subtitle="נסו לשנות פילטר או חיפוש" icon="storefront-outline" />
        ) : (
          list.map((b) => <BusinessCard key={b.id} item={b} />)
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: { paddingHorizontal: SPACING.md, paddingTop: SPACING.md, paddingBottom: SPACING.xs },
  screenTitle: { color: COLORS.textPrimary, fontSize: 28, fontWeight: "900", textAlign: "right", writingDirection: "rtl" },
  screenSub: { color: COLORS.textMuted, fontSize: 13, marginTop: 4, textAlign: "right" },
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
  chipsRow: { paddingVertical: SPACING.md },
});
