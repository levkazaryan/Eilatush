import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { api, openLink } from "../../api";
import { COLORS, SPACING } from "../../theme";
import { NewsCard, NewsT, FilterChip, EmptyState } from "../../components";

const TYPES: { key: string; label: string }[] = [
  { key: "", label: "הכל" },
  { key: "news", label: "חדשות" },
  { key: "alert", label: "מבזקים" },
  { key: "event", label: "אירועים" },
];

type SourceOption = { source_name: string; count: number };

export default function NewsScreen() {
  const [list, setList] = useState<NewsT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sourceType, setSourceType] = useState("");
  const [sourceName, setSourceName] = useState("");
  const [sources, setSources] = useState<SourceOption[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const router = useRouter();

  const formatLastUpdated = (iso?: string | null) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const now = new Date();
    const diffMin = Math.max(0, Math.round((now.getTime() - d.getTime()) / 60000));
    if (diffMin < 1) return "עכשיו";
    if (diffMin < 60) return `לפני ${diffMin} דק׳`;
    const sameDay = d.toDateString() === now.toDateString();
    const hh = d.getHours().toString().padStart(2, "0");
    const mm = d.getMinutes().toString().padStart(2, "0");
    if (sameDay) return `היום ${hh}:${mm}`;
    return d.toLocaleString("he-IL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  const loadSources = useCallback(async () => {
    try {
      const s = await api.newsSources();
      setSources(Array.isArray(s) ? s : []);
    } catch (e) {
      console.warn("sources", e);
    }
    try {
      const st = await api.newsStatus();
      setLastUpdated(st?.last_updated_at || null);
    } catch (e) {
      console.warn("status", e);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const data = await api.news({
        source: sourceType || undefined,
        source_name: sourceName || undefined,
      });
      setList(Array.isArray(data) ? data : []);
    } catch (e) {
      console.warn("load news", e);
      setList([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [sourceType, sourceName]);

  useEffect(() => {
    loadSources();
  }, [loadSources]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    loadSources();
    load();
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>חדשות מאילת</Text>
        <Text style={styles.screenSub}>
          {list.length > 0
            ? `${list.length} כתבות · מתעדכן כל שעה${lastUpdated ? ` · עדכון אחרון ב-${formatLastUpdated(lastUpdated)}` : ""}`
            : "עדכונים מהמקורות הרשמיים"}
        </Text>
      </View>

      {/* Source type filter */}
      <View style={styles.chipsRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: SPACING.md, flexDirection: "row-reverse" }}>
          {TYPES.map((s) => (
            <FilterChip
              key={s.key || "all"}
              label={s.label}
              active={sourceType === s.key}
              onPress={() => setSourceType(s.key)}
              testID={`news-type-${s.key || "all"}`}
            />
          ))}
        </ScrollView>
      </View>

      {/* Source name filter */}
      {sources.length > 0 && (
        <View style={[styles.chipsRow, { paddingTop: 4 }]}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: SPACING.md, flexDirection: "row-reverse" }}>
            <FilterChip
              label="כל המקורות"
              active={sourceName === ""}
              onPress={() => setSourceName("")}
              testID="news-src-all"
            />
            {sources.map((s) => (
              <FilterChip
                key={s.source_name}
                label={`${s.source_name} (${s.count})`}
                active={sourceName === s.source_name}
                onPress={() => setSourceName(s.source_name)}
                testID={`news-src-${s.source_name}`}
              />
            ))}
          </ScrollView>
        </View>
      )}

      <ScrollView
        contentContainerStyle={{ paddingTop: SPACING.md, paddingBottom: 120 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />}
      >
        {loading ? (
          <View style={{ paddingVertical: 40 }}>
            <ActivityIndicator color={COLORS.primary} />
          </View>
        ) : list.length === 0 ? (
          <EmptyState title="אין חדשות" subtitle="נסה לרענן או לבחור קטגוריה/מקור אחר" icon="newspaper-outline" />
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
