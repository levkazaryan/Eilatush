'use client';

import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import { api, openLink } from "../../api";
import { COLORS, SPACING } from "../../theme";
import { NewsCard, NewsT, FilterChip, EmptyState } from "../../components";
import { trackScreen, trackNewsOutbound } from "../../utils/analytics";

type SourceOption = { source_name: string; count: number };
type CategoryOption = { slug: string; label: string; emoji: string; count: number };

export default function NewsScreen() {
  const [list, setList] = useState<NewsT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [category, setCategory] = useState<string>("all");
  const [sourceName, setSourceName] = useState<string>("");
  const [categories, setCategories] = useState<CategoryOption[]>([]);
  const [sources, setSources] = useState<SourceOption[]>([]);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const router = useRouter();

  const formatLastUpdated = (iso?: string | null) => {
    if (!iso) return "";
    // Backend stores UTC. Append "Z" if no tz suffix so JS parses it as UTC.
    const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z";
    const d = new Date(normalized);
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

  const loadMeta = useCallback(async () => {
    try {
      const [cats, srcs, status] = await Promise.all([
        api.newsCategories(),
        api.newsSources(),
        api.newsStatus(),
      ]);
      setCategories(Array.isArray(cats) ? cats : []);
      setSources(Array.isArray(srcs) ? srcs : []);
      setLastUpdated(status?.last_updated_at || null);
    } catch (e) {
      console.warn("loadMeta", e);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const data = await api.news({
        category: category && category !== "all" ? category : undefined,
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
  }, [category, sourceName]);

  useEffect(() => {
    trackScreen("news");
    loadMeta();
  }, [loadMeta]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    loadMeta();
    load();
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>חדשות מאילת</Text>
        <Text style={styles.screenSub}>
          {list.length > 0
            ? `${list.length} כתבות · מתעדכן כל שעה${lastUpdated ? ` · נבדק ${formatLastUpdated(lastUpdated)}` : ""}`
            : "עדכונים מהמקורות הרשמיים"}
        </Text>
      </View>

      {/* Category filter (subject / topic) */}
      {categories.length > 0 && (
        <View style={styles.chipsRow}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipsContent}
            style={{ direction: "rtl" as any }}
          >
            {categories.map((c) => (
              <FilterChip
                key={c.slug}
                label={`${c.emoji} ${c.label}${c.count > 0 ? ` (${c.count})` : ""}`}
                active={category === c.slug}
                onPress={() => setCategory(c.slug)}
                testID={`news-cat-${c.slug}`}
              />
            ))}
          </ScrollView>
        </View>
      )}

      {/* Source name filter */}
      {sources.length > 0 && (
        <View style={[styles.chipsRow, { paddingTop: 4 }]}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipsContent}
            style={{ direction: "rtl" as any }}
          >
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
              onSourcePress={() => {
                if (n.source_url) {
                  trackNewsOutbound(n.id);
                  openLink(n.source_url);
                }
              }}
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
  chipsContent: {
    paddingHorizontal: SPACING.md,
    flexDirection: "row",
    justifyContent: "flex-start",
  },
});
