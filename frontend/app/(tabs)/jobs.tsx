import React, { useCallback, useEffect, useMemo, useState } from "react";
import { View, Text, StyleSheet, ScrollView, RefreshControl, ActivityIndicator } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { api } from "../../api";
import { COLORS, SPACING } from "../../theme";
import { JobCard, JobT, FilterChip, EmptyState } from "../../components";

const URGENCIES: { key: string; label: string }[] = [
  { key: "", label: "הכל" },
  { key: "now", label: "🔥 עכשיו" },
  { key: "soon", label: "בקרוב" },
  { key: "this_week", label: "השבוע" },
];

const CATS: { key: string; label: string }[] = [
  { key: "", label: "כל הענפים" },
  { key: "hotel", label: "מלונאות" },
  { key: "restaurant", label: "מסעדות" },
  { key: "tourism", label: "תיירות" },
  { key: "retail", label: "קמעונאות" },
  { key: "service", label: "שירותים" },
];

export default function JobsScreen() {
  const [list, setList] = useState<JobT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [urgency, setUrgency] = useState("");
  const [category, setCategory] = useState("");

  const load = useCallback(async () => {
    try {
      const data = await api.jobs({ urgency: urgency || undefined, category: category || undefined });
      setList(Array.isArray(data) ? data : []);
    } catch (e) {
      console.warn("load jobs", e);
      setList([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [urgency, category]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const nowCount = useMemo(() => list.filter((j) => j.urgency === "now").length, [list]);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>משרות באילת</Text>
        <Text style={styles.screenSub}>
          {nowCount > 0 ? `🔥 ${nowCount} משרות דחופות · התחלה מיידית` : `${list.length} משרות · הגשה בוואטסאפ`}
        </Text>
      </View>

      <View style={styles.chipsRow}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: SPACING.md, flexDirection: "row-reverse" }}>
          {URGENCIES.map((u) => (
            <FilterChip
              key={u.key || "all"}
              label={u.label}
              active={urgency === u.key}
              onPress={() => setUrgency(u.key)}
              testID={`job-urg-${u.key || "all"}`}
            />
          ))}
        </ScrollView>
      </View>

      <View style={[styles.chipsRow, { paddingTop: 4 }]}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ paddingHorizontal: SPACING.md, flexDirection: "row-reverse" }}>
          {CATS.map((c) => (
            <FilterChip
              key={c.key || "all"}
              label={c.label}
              active={category === c.key}
              onPress={() => setCategory(c.key)}
              testID={`job-cat-${c.key || "all"}`}
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
          <EmptyState title="אין משרות" subtitle="נסו לשנות את הפילטר" icon="briefcase-outline" />
        ) : (
          list.map((j) => <JobCard key={j.id} item={j} />)
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
