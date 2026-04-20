'use client';

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
  Pressable,
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
  const [days, setDays] = useState<{ date: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [band, setBand] = useState<(typeof BANDS)[number]["key"]>("all");
  const [category, setCategory] = useState<string>("");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const insets = useSafeAreaInsets();

  const load = useCallback(async () => {
    try {
      const [data, dayList] = await Promise.all([
        api.events({
          category: category || undefined,
          date: selectedDate || undefined,
        }),
        api.eventDays(),
      ]);
      setEvents(Array.isArray(data) ? data : []);
      setDays(Array.isArray(dayList) ? dayList : []);
    } catch (e) {
      console.warn("load events", e);
      setEvents([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [category, selectedDate]);

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
        />

        <View style={styles.chipsRow}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.chipsScrollContent}
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

        {/* Day strip — pick a date to filter events */}
        <DayStrip
          days={days}
          selected={selectedDate}
          onSelect={(d) => setSelectedDate(d)}
        />

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

// ---------------------------------------------------------------------------
// Day strip — horizontal scrollable date selector
// ---------------------------------------------------------------------------
const HEB_DAY_SHORT = ["א'", "ב'", "ג'", "ד'", "ה'", "ו'", "ש'"];

function DayStrip({
  days,
  selected,
  onSelect,
}: {
  days: { date: string; count: number }[];
  selected: string | null;
  onSelect: (d: string | null) => void;
}) {
  const items = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const range: { date: string; count: number; isToday: boolean }[] = [];
    const toLocalISO = (d: Date) => {
      // YYYY-MM-DD in local time (avoid toISOString which returns UTC and
      // shifts us a day backwards in Israel after midnight local).
      const y = d.getFullYear();
      const m = String(d.getMonth() + 1).padStart(2, "0");
      const day = String(d.getDate()).padStart(2, "0");
      return `${y}-${m}-${day}`;
    };
    for (let i = 0; i < 14; i++) {
      const dt = new Date(today);
      dt.setDate(today.getDate() + i);
      const iso = toLocalISO(dt);
      const count = days.find((d) => d.date === iso)?.count ?? 0;
      range.push({ date: iso, count, isToday: i === 0 });
    }
    return range;
  }, [days]);

  return (
    <View style={styles.dayStripRow}>
      <Text style={styles.dayStripLabel}>לוח שנה</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.dayStripContent}
      >
        <Pressable
          onPress={() => onSelect(null)}
          style={({ pressed }) => [
            styles.dayCell,
            selected === null && styles.dayCellActive,
            pressed && { opacity: 0.7 },
          ]}
          testID="day-cell-all"
        >
          <Ionicons
            name="sparkles"
            size={16}
            color={selected === null ? "#fff" : COLORS.primary}
          />
          <Text style={[styles.dayCellDay, selected === null && styles.dayCellTextActive]}>הכל</Text>
        </Pressable>
        {items.map((d) => {
          const dt = new Date(d.date + "T12:00:00");
          const active = selected === d.date;
          return (
            <Pressable
              key={d.date}
              onPress={() => onSelect(d.date)}
              style={({ pressed }) => [
                styles.dayCell,
                active && styles.dayCellActive,
                d.count === 0 && !active && styles.dayCellEmpty,
                pressed && { opacity: 0.7 },
              ]}
              testID={`day-cell-${d.date}`}
            >
              <Text style={[styles.dayCellDay, active && styles.dayCellTextActive]}>
                {d.isToday ? "היום" : HEB_DAY_SHORT[dt.getDay()]}
              </Text>
              <Text style={[styles.dayCellNum, active && styles.dayCellTextActive]}>
                {dt.getDate()}
              </Text>
              {d.count > 0 ? (
                <View style={[styles.dayCountBadge, active && styles.dayCountBadgeActive]}>
                  <Text style={[styles.dayCountText, active && { color: COLORS.primary }]}>
                    {d.count}
                  </Text>
                </View>
              ) : (
                <View style={{ height: 14 }} />
              )}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
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
  chipsRow: {
    paddingTop: SPACING.md,
    paddingBottom: 4,
  },
  chipsScrollContent: {
    paddingHorizontal: SPACING.md,
    flexDirection: "row",
  },
  chipsFlex: {
    flexDirection: "row",
    paddingHorizontal: SPACING.md,
    justifyContent: "flex-start",
    gap: 0,
  },

  // Day strip
  dayStripRow: {
    paddingTop: 4,
    paddingBottom: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: COLORS.border,
  },
  dayStripLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: COLORS.textMuted,
    textAlign: "right",
    paddingHorizontal: SPACING.md,
    marginBottom: 6,
    writingDirection: "rtl",
  },
  dayStripContent: {
    paddingHorizontal: SPACING.md,
    flexDirection: "row",
    gap: 8,
  },
  dayCell: {
    width: 58,
    paddingVertical: 10,
    borderRadius: RADIUS.md,
    backgroundColor: COLORS.surface,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignItems: "center",
    gap: 2,
  },
  dayCellActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  dayCellEmpty: {
    opacity: 0.45,
  },
  dayCellDay: {
    fontSize: 12,
    fontWeight: "700",
    color: COLORS.textSecondary,
  },
  dayCellNum: {
    fontSize: 18,
    fontWeight: "900",
    color: COLORS.textPrimary,
  },
  dayCellTextActive: { color: "#fff" },
  dayCountBadge: {
    minWidth: 22,
    paddingHorizontal: 6,
    paddingVertical: 1,
    borderRadius: 10,
    backgroundColor: "rgba(20,184,179,0.15)",
    alignItems: "center",
    marginTop: 2,
  },
  dayCountBadgeActive: {
    backgroundColor: "#fff",
  },
  dayCountText: {
    fontSize: 11,
    fontWeight: "800",
    color: COLORS.primary,
  },
});
