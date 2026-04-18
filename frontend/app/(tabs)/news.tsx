import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { api, openLink } from "../../api";
import { COLORS, SPACING } from "../../theme";
import { NewsCard, NewsT, FilterChip, EmptyState } from "../../components";

const SOURCES: { key: string; label: string }[] = [
  { key: "", label: "הכל" },
  { key: "news", label: "חדשות" },
  { key: "alert", label: "מבזקים" },
  { key: "event", label: "אירועים" },
];

export default function NewsScreen() {
  const [list, setList] = useState<NewsT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [source, setSource] = useState("");
  const router = useRouter();

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
        <Text style={styles.screenTitle}>חדשות מאילת</Text>
        <Text style={styles.screenSub}>
          {list.length > 0 ? `${list.length} כתבות · מתעדכן אוטומטית כל שעה` : "עדכונים מהמקורות הרשמיים"}
        </Text>
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
          <EmptyState title="אין חדשות" subtitle="נסה לרענן או לבחור קטגוריה אחרת" icon="newspaper-outline" />
        ) : (
          list.map((n) => (
            <NewsCard
              key={n.id}
              item={n}
              onPress={() => router.push(`/article/${n.id}`)}
              onSourcePress={() => n.source_url && openLink(n.source_url)}
            />
          ))
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
