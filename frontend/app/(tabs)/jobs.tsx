import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  ActivityIndicator,
  Modal,
  Pressable,
  TouchableOpacity,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { api, openLink } from "../../api";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { JobCard, JobT, EmptyState } from "../../components";

type JobCategory = { slug: string; label: string; emoji: string; count: number };
type JobSource = { source: string; source_name: string; count: number };

const DATE_OPTS: { key: string; label: string }[] = [
  { key: "", label: "כל התאריכים" },
  { key: "today", label: "היום" },
  { key: "3d", label: "3 ימים אחרונים" },
  { key: "week", label: "השבוע" },
  { key: "month", label: "החודש" },
];

const JOB_TYPE_OPTS: { key: string; label: string }[] = [
  { key: "", label: "כל סוגי המשרה" },
  { key: "full_time", label: "משרה מלאה" },
  { key: "part_time", label: "משרה חלקית" },
  { key: "shifts", label: "משמרות" },
  { key: "temporary", label: "זמני / עונתי" },
  { key: "remote", label: "מהבית" },
];

const EXPERIENCE_OPTS: { key: string; label: string }[] = [
  { key: "", label: "הכל" },
  { key: "none", label: "ללא ניסיון" },
  { key: "required", label: "דרוש ניסיון" },
];

export default function JobsScreen() {
  const [list, setList] = useState<JobT[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  // Filters
  const [category, setCategory] = useState("");
  const [dateRange, setDateRange] = useState("");
  const [jobType, setJobType] = useState("");
  const [experience, setExperience] = useState("");
  const [source, setSource] = useState("");

  // Dropdowns data
  const [categories, setCategories] = useState<JobCategory[]>([]);
  const [sources, setSources] = useState<JobSource[]>([]);

  // Modal state: null = closed, else which filter is open
  const [openFilter, setOpenFilter] = useState<
    null | "category" | "date" | "job_type" | "experience" | "source"
  >(null);

  const loadMeta = useCallback(async () => {
    try {
      const [cats, srcs, status] = await Promise.all([
        api.jobsCategories(),
        api.jobsSources(),
        api.jobsStatus(),
      ]);
      setCategories(Array.isArray(cats) ? cats : []);
      setSources(Array.isArray(srcs) ? srcs : []);
      setLastUpdated(status?.last_updated_at || null);
    } catch (e) {
      console.warn("loadMeta jobs", e);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const data = await api.jobs({
        category: category || undefined,
        date_range: dateRange || undefined,
        job_type: jobType || undefined,
        experience: experience || undefined,
        source: source || undefined,
      });
      setList(Array.isArray(data) ? data : []);
    } catch (e) {
      console.warn("load jobs", e);
      setList([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [category, dateRange, jobType, experience, source]);

  useEffect(() => {
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

  const activeCount = [category, dateRange, jobType, experience, source].filter(Boolean).length;

  const formatLastUpdated = (iso?: string | null) => {
    if (!iso) return "";
    const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z";
    const d = new Date(normalized);
    if (isNaN(d.getTime())) return "";
    const now = new Date();
    const diffMin = Math.max(0, Math.round((now.getTime() - d.getTime()) / 60000));
    if (diffMin < 1) return "עכשיו";
    if (diffMin < 60) return `לפני ${diffMin} דק׳`;
    const hh = d.getHours().toString().padStart(2, "0");
    const mm = d.getMinutes().toString().padStart(2, "0");
    if (d.toDateString() === now.toDateString()) return `היום ${hh}:${mm}`;
    return d.toLocaleString("he-IL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  const clearAll = () => {
    setCategory("");
    setDateRange("");
    setJobType("");
    setExperience("");
    setSource("");
  };

  // Current label helpers
  const currentCategoryLabel =
    categories.find((c) => c.slug === category)?.label || "כל התחומים";
  const currentCategoryEmoji = categories.find((c) => c.slug === category)?.emoji || "🏷️";
  const currentDateLabel = DATE_OPTS.find((d) => d.key === dateRange)?.label || "כל התאריכים";
  const currentJobTypeLabel = JOB_TYPE_OPTS.find((d) => d.key === jobType)?.label || "כל סוגי המשרה";
  const currentExpLabel = EXPERIENCE_OPTS.find((d) => d.key === experience)?.label || "ניסיון (הכל)";
  const currentSourceLabel = sources.find((s) => s.source === source)?.source_name || "כל המקורות";

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.screenTitle}>משרות באילת</Text>
        <Text style={styles.screenSub}>
          {list.length > 0
            ? `${list.length} משרות · מתעדכן כל שעה${lastUpdated ? ` · נבדק ${formatLastUpdated(lastUpdated)}` : ""}`
            : "מאגר משרות מהאתרים המובילים באילת"}
        </Text>
      </View>

      {/* Filter dropdowns row */}
      <View style={styles.dropdownRowWrapper}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.dropdownRow}
          style={{ direction: "rtl" as any }}
        >
          <DropdownButton
            icon="pricetags-outline"
            label={currentCategoryLabel}
            emoji={category ? currentCategoryEmoji : undefined}
            active={!!category}
            onPress={() => setOpenFilter("category")}
          />
          <DropdownButton
            icon="calendar-outline"
            label={currentDateLabel}
            active={!!dateRange}
            onPress={() => setOpenFilter("date")}
          />
          <DropdownButton
            icon="time-outline"
            label={currentJobTypeLabel}
            active={!!jobType}
            onPress={() => setOpenFilter("job_type")}
          />
          <DropdownButton
            icon="school-outline"
            label={currentExpLabel}
            active={!!experience}
            onPress={() => setOpenFilter("experience")}
          />
          <DropdownButton
            icon="open-outline"
            label={currentSourceLabel}
            active={!!source}
            onPress={() => setOpenFilter("source")}
          />
          {activeCount > 0 ? (
            <Pressable onPress={clearAll} style={styles.clearBtn}>
              <Ionicons name="close-circle" size={14} color={COLORS.primary} />
              <Text style={styles.clearBtnText}>נקה ({activeCount})</Text>
            </Pressable>
          ) : null}
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
          <EmptyState
            title="אין משרות מתאימות"
            subtitle="נסו לשנות או לאפס את הסינון"
            icon="briefcase-outline"
          />
        ) : (
          list.map((j) => (
            <JobCard
              key={j.id}
              item={j}
              onPress={() => j.source_url && openLink(j.source_url)}
            />
          ))
        )}
      </ScrollView>

      {/* Filter BottomSheet modal */}
      <Modal
        visible={openFilter !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setOpenFilter(null)}
      >
        <Pressable style={styles.modalBackdrop} onPress={() => setOpenFilter(null)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <View style={styles.sheetHandle} />
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>
                {openFilter === "category" && "🏷️ בחר/י תחום"}
                {openFilter === "date" && "📅 מתי הועלה"}
                {openFilter === "job_type" && "⏰ סוג משרה"}
                {openFilter === "experience" && "🎓 דרישת ניסיון"}
                {openFilter === "source" && "🔗 מקור"}
              </Text>
              <Pressable onPress={() => setOpenFilter(null)} hitSlop={10}>
                <Ionicons name="close" size={24} color={COLORS.textSecondary} />
              </Pressable>
            </View>
            <ScrollView contentContainerStyle={{ paddingBottom: 30 }}>
              {openFilter === "category" && (
                <>
                  <OptionRow
                    label="כל התחומים"
                    emoji="🏷️"
                    count={categories.find((c) => c.slug === "all")?.count}
                    selected={category === ""}
                    onPress={() => { setCategory(""); setOpenFilter(null); }}
                  />
                  {categories
                    .filter((c) => c.slug !== "all")
                    .map((c) => (
                      <OptionRow
                        key={c.slug}
                        label={c.label}
                        emoji={c.emoji}
                        count={c.count}
                        selected={category === c.slug}
                        onPress={() => { setCategory(c.slug); setOpenFilter(null); }}
                      />
                    ))}
                </>
              )}
              {openFilter === "date" &&
                DATE_OPTS.map((o) => (
                  <OptionRow
                    key={o.key || "all"}
                    label={o.label}
                    selected={dateRange === o.key}
                    onPress={() => { setDateRange(o.key); setOpenFilter(null); }}
                  />
                ))}
              {openFilter === "job_type" &&
                JOB_TYPE_OPTS.map((o) => (
                  <OptionRow
                    key={o.key || "all"}
                    label={o.label}
                    selected={jobType === o.key}
                    onPress={() => { setJobType(o.key); setOpenFilter(null); }}
                  />
                ))}
              {openFilter === "experience" &&
                EXPERIENCE_OPTS.map((o) => (
                  <OptionRow
                    key={o.key || "all"}
                    label={o.label}
                    selected={experience === o.key}
                    onPress={() => { setExperience(o.key); setOpenFilter(null); }}
                  />
                ))}
              {openFilter === "source" && (
                <>
                  <OptionRow
                    label="כל המקורות"
                    selected={source === ""}
                    onPress={() => { setSource(""); setOpenFilter(null); }}
                  />
                  {sources.map((s) => (
                    <OptionRow
                      key={s.source}
                      label={s.source_name}
                      count={s.count}
                      selected={source === s.source}
                      onPress={() => { setSource(s.source); setOpenFilter(null); }}
                    />
                  ))}
                </>
              )}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

function DropdownButton({
  icon,
  label,
  emoji,
  active,
  onPress,
}: {
  icon: any;
  label: string;
  emoji?: string;
  active?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.dropdownBtn,
        active && styles.dropdownBtnActive,
        pressed && { opacity: 0.75 },
      ]}
    >
      {emoji ? (
        <Text style={{ fontSize: 14 }}>{emoji}</Text>
      ) : (
        <Ionicons
          name={icon}
          size={14}
          color={active ? COLORS.primary : COLORS.textSecondary}
        />
      )}
      <Text style={[styles.dropdownBtnText, active && { color: COLORS.primary }]} numberOfLines={1}>
        {label}
      </Text>
      <Ionicons
        name="chevron-down"
        size={12}
        color={active ? COLORS.primary : COLORS.textMuted}
      />
    </Pressable>
  );
}

function OptionRow({
  label,
  emoji,
  count,
  selected,
  onPress,
}: {
  label: string;
  emoji?: string;
  count?: number;
  selected?: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.optionRow,
        selected && styles.optionRowSelected,
        pressed && { opacity: 0.75 },
      ]}
    >
      <Ionicons
        name={selected ? "checkmark-circle" : "ellipse-outline"}
        size={20}
        color={selected ? COLORS.primary : COLORS.textMuted}
      />
      <Text style={[styles.optionLabel, selected && { color: COLORS.primary, fontWeight: "900" }]} numberOfLines={1}>
        {emoji ? `${emoji} ` : ""}{label}
      </Text>
      {typeof count === "number" && count > 0 ? (
        <Text style={styles.optionCount}>{count}</Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: { paddingHorizontal: SPACING.md, paddingTop: SPACING.md, paddingBottom: SPACING.sm },
  screenTitle: {
    color: COLORS.textPrimary,
    fontSize: 28,
    fontWeight: "900",
    textAlign: "right",
    writingDirection: "rtl",
  },
  screenSub: { color: COLORS.textMuted, fontSize: 13, marginTop: 4, textAlign: "right" },

  dropdownRowWrapper: {
    paddingVertical: 2,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: COLORS.bg,
  },
  dropdownRow: {
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.sm,
    gap: 8,
    flexDirection: "row",
    alignItems: "center",
  },
  dropdownBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: RADIUS.pill,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: COLORS.border,
    gap: 6,
    maxWidth: 180,
  },
  dropdownBtnActive: {
    backgroundColor: "rgba(230,57,70,0.08)",
    borderColor: "rgba(230,57,70,0.40)",
  },
  dropdownBtnText: {
    color: COLORS.textSecondary,
    fontSize: 12,
    fontWeight: "700",
    maxWidth: 120,
  },

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

  // Modal / bottom sheet
  modalBackdrop: {
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
  },

  optionRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 6,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(15,23,42,0.05)",
    gap: 10,
  },
  optionRowSelected: {
    backgroundColor: "rgba(230,57,70,0.06)",
  },
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
});
