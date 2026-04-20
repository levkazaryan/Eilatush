'use client';

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../api";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { EventCard, EventT, SectionHeader, FilterChip, EmptyState } from "../../components";
import { WeatherHero } from "../../components/WeatherHero";

const BANDS: { key: "all" | "now" | "tonight" | "later"; label: string }[] = [
  { key: "all", label: "הכל" },
  { key: "now", label: "עכשיו" },
  { key: "tonight", label: "הערב" },
  { key: "later", label: "בהמשך" },
];

const CATEGORIES: { key: string; label: string }[] = [
  { key: "", label: "כל הסוגים" },
  { key: "party", label: "מסיבות" },
  { key: "concert", label: "הופעות" },
  { key: "show", label: "מופעים" },
  { key: "activity", label: "פעילות" },
  { key: "food", label: "אוכל" },
  { key: "sport", label: "ספורט" },
];

export default function HomeScreen() {
  const [events, setEvents] = useState<EventT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [band, setBand] = useState<(typeof BANDS)[number]["key"]>("all");
  const [category, setCategory] = useState<string>("");
  const insets = useSafeAreaInsets();

  const load = useCallback(async () => {
    try {
      const data = await api.events({ category: category || undefined });
      setEvents(Array.isArray(data) ? data : []);
    } catch (e) {
      console.warn("load events", e);
      setEvents([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [category]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const onRefresh = () => {
    setRefreshing(true);
    load();
  };

  const filtered = useMemo(() => {
    if (band === "all") return events;
    return events.filter((e) => e.band === band);
  }, [events, band]);

  const grouped = useMemo(() => {
    const groups: Record<string, EventT[]> = { now: [], tonight: [], later: [] };
    for (const e of filtered) {
      const b = (e.band as string) || "later";
      if (!groups[b]) groups[b] = [];
      groups[b].push(e);
    }
    return groups;
  }, [filtered]);

  const nowCount = events.filter((e) => e.band === "now").length;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <ScrollView
        contentContainerStyle={{ paddingBottom: 120 }}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.primary} />
        }
      >
        <WeatherHero
          title="מה קורה עכשיו באילת?"
          subtitle={
            nowCount > 0
              ? `${nowCount} אירועים קורים ממש עכשיו · גלול למטה`
              : "מסיבות, הופעות, פעילויות - הכל במקום אחד"
          }
          brand={
            <View style={styles.brandRow}>
              <View style={styles.brandDot}>
                <Ionicons name="sparkles" size={16} color="#fff" />
              </View>
              <Text style={styles.brandText}>אילתוש</Text>
            </View>
          }
        />

        <View style={styles.chipsRow}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ paddingHorizontal: SPACING.md, flexDirection: "row-reverse" }}
          >
            {BANDS.map((b) => (
              <FilterChip
                key={b.key}
                label={b.label}
                active={band === b.key}
                onPress={() => setBand(b.key)}
                testID={`band-chip-${b.key}`}
              />
            ))}
          </ScrollView>
        </View>

        <View style={[styles.chipsRow, { marginTop: 4 }]}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ paddingHorizontal: SPACING.md, flexDirection: "row-reverse" }}
          >
            {CATEGORIES.map((c) => (
              <FilterChip
                key={c.key || "all"}
                label={c.label}
                active={category === c.key}
                onPress={() => setCategory(c.key)}
                testID={`cat-chip-${c.key || "all"}`}
              />
            ))}
          </ScrollView>
        </View>

        {loading ? (
          <View style={{ paddingVertical: 40 }}>
            <ActivityIndicator color={COLORS.primary} />
          </View>
        ) : filtered.length === 0 ? (
          <EmptyState
            title="אין אירועים כרגע"
            subtitle="נסו לסנן אחרת או חזרו מאוחר יותר"
            icon="calendar-outline"
          />
        ) : band === "all" ? (
          <>
            {grouped.now && grouped.now.length > 0 && (
              <>
                <SectionHeader title="🔥 עכשיו" subtitle="תתפסו את הרגע" />
                {grouped.now.map((e) => (
                  <EventCard key={e.id} item={e} />
                ))}
              </>
            )}
            {grouped.tonight && grouped.tonight.length > 0 && (
              <>
                <SectionHeader title="הלילה" subtitle="מתחילים בעוד כמה שעות" />
                {grouped.tonight.map((e) => (
                  <EventCard key={e.id} item={e} />
                ))}
              </>
            )}
            {grouped.later && grouped.later.length > 0 && (
              <>
                <SectionHeader title="בהמשך" />
                {grouped.later.map((e) => (
                  <EventCard key={e.id} item={e} />
                ))}
              </>
            )}
          </>
        ) : (
          <View style={{ marginTop: SPACING.md }}>
            {filtered.map((e) => (
              <EventCard key={e.id} item={e} />
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  hero: {
    height: 220,
    backgroundColor: COLORS.surface,
    justifyContent: "flex-end",
  },
  heroOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(12,12,18,0.55)",
  },
  heroContent: {
    padding: SPACING.lg,
  },
  brandRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 8,
    marginBottom: 10,
  },
  brandDot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: COLORS.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  brandText: { color: "#fff", fontSize: 16, fontWeight: "900", letterSpacing: 0.5 },
  heroTitle: {
    color: "#fff",
    fontSize: 30,
    fontWeight: "900",
    textAlign: "right",
    writingDirection: "rtl",
  },
  heroSub: {
    color: COLORS.textPrimary,
    fontSize: 14,
    marginTop: 6,
    textAlign: "right",
    writingDirection: "rtl",
    opacity: 0.85,
  },
  chipsRow: {
    paddingTop: SPACING.md,
    paddingBottom: 4,
  },
});
