import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { api } from "../../api";
import { COLORS, SPACING } from "../../theme";
import { NewsCard, NewsT, FilterChip, EmptyState } from "../../components";

const SOURCES: { key: string; label: string }[] = [
  { key: "", label: "הכל" },
  { key: "municipality", label: "עירייה" },
  { key: "alert", label: "התראות" },
  { key: "event", label: "אירועים" },
];

export default function NewsScreen() {
  const [list, setList] = useState<NewsT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [source, setSource] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api.news({ source: source || undefined });
      setList(Array.isArray(data) ? data : []);
    } catch (e) {
      console.warn("load news", e);
      setList([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [source]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>חדשות מקומיות</Text>
        <Text style={styles.screenSub}>עדכונים רשמיים · בלי רעש · בלי ספאם</Text>
      </View>

      <View style={styles.chipsRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: SPACING.md, flexDirection: "row-reverse" }}>
          {SOURCES.map((s) => (
            <FilterChip
              key={s.key || "all"}
              label={s.label}
              active={source === s.key}
              onPress={() => setSource(s.key)}
              testID={`news-src-${s.key || "all"}`}
            />
          ))}
        </ScrollView>
      </View>

      <ScrollView
        contentContainerStyle={{ paddingTop: SPACING.md, paddingBottom: 120 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />}
      >
        {loading ? (
          <View style={{ paddingVertical: 40 }}>
            <ActivityIndicator color={COLORS.primary} />
          </View>
        ) : list.length === 0 ? (
          <EmptyState title="אין מבזקים" subtitle="חזרו מאוחר יותר" icon="newspaper-outline" />
        ) : (
          list.map((n) => <NewsCard key={n.id} item={n} />)
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: { paddingHorizontal: SPACING.md, paddingTop: SPACING.md, paddingBottom: SPACING.sm },
  screenTitle: { color: COLORS.textPrimary, fontSize: 28, fontWeight: "900", textAlign: "right", writingDirection: "rtl" },
  screenSub: { color: COLORS.textMuted, fontSize: 13, marginTop: 4, textAlign: "right" },
  chipsRow: { paddingVertical: SPACING.sm },
});
