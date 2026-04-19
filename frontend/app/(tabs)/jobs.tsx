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
import { useRouter } from "expo-router";
import { api } from "../../api";
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
  const router = useRouter();

  // Multi-select filters (arrays). Empty array = "all".
  const [category, setCategory] = useState<string[]>([]);
  const [dateRange, setDateRange] = useState(""); // single
  const [jobType, setJobType] = useState<string[]>([]);
  const [experience, setExperience] = useState<string[]>([]);
  const [source, setSource] = useState<string[]>([]);

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
        category: category.length ? category : undefined,
        date_range: dateRange || undefined,
        job_type: jobType.length ? jobType : undefined,
        experience: experience.length ? experience : undefined,
        source: source.length ? source : undefined,
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

  const activeCount =
    category.length + (dateRange ? 1 : 0) + jobType.length + experience.length + source.length;

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
    setCategory([]);
    setDateRange("");
    setJobType([]);
    setExperience([]);
    setSource([]);
  };

  // Toggle helper for multi-select filters
  const toggle = (arr: string[], setter: (v: string[]) => void, value: string) => {
    setter(arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value]);
  };

  // Build a human label for a multi-select dropdown button
  const buildLabel = (
    selected: string[],
    allLabel: string,
    optionLabel: (key: string) => string,
  ) => {
    if (selected.length === 0) return allLabel;
    if (selected.length === 1) return optionLabel(selected[0]);
    return `${optionLabel(selected[0])} +${selected.length - 1}`;
  };

  // Current label helpers
  const catLabelOf = (slug: string) => {
    const c = categories.find((c) => c.slug === slug);
    return c ? `${c.emoji} ${c.label}` : slug;
  };
  const currentCategoryLabel = buildLabel(category, "כל התחומים", catLabelOf);
  const currentDateLabel = DATE_OPTS.find((d) => d.key === dateRange)?.label || "כל התאריכים";
  const currentJobTypeLabel = buildLabel(
    jobType,
    "כל סוגי המשרה",
    (k) => JOB_TYPE_OPTS.find((o) => o.key === k)?.label || k,
  );
  const currentExpLabel = buildLabel(
    experience,
    "ניסיון (הכל)",
    (k) => EXPERIENCE_OPTS.find((o) => o.key === k)?.label || k,
  );
  const currentSourceLabel = buildLabel(
    source,
    "כל המקורות",
    (k) => sources.find((s) => s.source === k)?.source_name || k,
  );

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
            active={category.length > 0}
            badge={category.length > 1 ? category.length : undefined}
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
            active={jobType.length > 0}
            badge={jobType.length > 1 ? jobType.length : undefined}
            onPress={() => setOpenFilter("job_type")}
          />
          <DropdownButton
            icon="school-outline"
            label={currentExpLabel}
            active={experience.length > 0}
            badge={experience.length > 1 ? experience.length : undefined}
            onPress={() => setOpenFilter("experience")}
          />
          <DropdownButton
            icon="open-outline"
            label={currentSourceLabel}
            active={source.length > 0}
            badge={source.length > 1 ? source.length : undefined}
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
              onPress={() => router.push(`/job/${j.id}`)}
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
                {openFilter === "category" && "🏷️ בחר/י תחומים"}
                {openFilter === "date" && "📅 מתי הועלה"}
                {openFilter === "job_type" && "⏰ סוג משרה"}
                {openFilter === "experience" && "🎓 דרישת ניסיון"}
                {openFilter === "source" && "🔗 מקורות"}
              </Text>
              <View style={{ flexDirection: "row-reverse", gap: 10, alignItems: "center" }}>
                {/* Clear selections for this filter only (not for date_range) */}
                {openFilter && openFilter !== "date" && (
                  ((openFilter === "category" && category.length > 0) ||
                   (openFilter === "job_type" && jobType.length > 0) ||
                   (openFilter === "experience" && experience.length > 0) ||
                   (openFilter === "source" && source.length > 0)) ? (
                    <Pressable
                      onPress={() => {
                        if (openFilter === "category") setCategory([]);
                        else if (openFilter === "job_type") setJobType([]);
                        else if (openFilter === "experience") setExperience([]);
                        else if (openFilter === "source") setSource([]);
                      }}
                      hitSlop={8}
                    >
                      <Text style={styles.sheetClearText}>נקה</Text>
                    </Pressable>
                  ) : null
                )}
                <Pressable onPress={() => setOpenFilter(null)} hitSlop={10}>
                  <Ionicons name="close" size={24} color={COLORS.textSecondary} />
                </Pressable>
              </View>
            </View>
            {openFilter && openFilter !== "date" ? (
              <Text style={styles.sheetSub}>אפשר לבחור כמה אפשרויות</Text>
            ) : null}
            <ScrollView contentContainerStyle={{ paddingBottom: 30 }}>
              {openFilter === "category" &&
                categories
                  .filter((c) => c.slug !== "all")
                  .map((c) => (
                    <OptionRow
                      key={c.slug}
                      label={c.label}
                      emoji={c.emoji}
                      count={c.count}
                      selected={category.includes(c.slug)}
                      multi
                      onPress={() => toggle(category, setCategory, c.slug)}
                    />
                  ))}
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
                JOB_TYPE_OPTS.filter((o) => o.key).map((o) => (
                  <OptionRow
                    key={o.key}
                    label={o.label}
                    selected={jobType.includes(o.key)}
                    multi
                    onPress={() => toggle(jobType, setJobType, o.key)}
                  />
                ))}
              {openFilter === "experience" &&
                EXPERIENCE_OPTS.filter((o) => o.key).map((o) => (
                  <OptionRow
                    key={o.key}
                    label={o.label}
                    selected={experience.includes(o.key)}
                    multi
                    onPress={() => toggle(experience, setExperience, o.key)}
                  />
                ))}
              {openFilter === "source" &&
                sources.map((s) => (
                  <OptionRow
                    key={s.source}
                    label={s.source_name}
                    count={s.count}
                    selected={source.includes(s.source)}
                    multi
                    onPress={() => toggle(source, setSource, s.source)}
                  />
                ))}
            </ScrollView>
            {openFilter && openFilter !== "date" ? (
              <Pressable
                onPress={() => setOpenFilter(null)}
                style={({ pressed }) => [styles.applyBtn, pressed && { opacity: 0.85 }]}
              >
                <Text style={styles.applyBtnText}>
                  הצג {list.length} משרות
                </Text>
              </Pressable>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

function DropdownButton({
  icon,
  label,
  badge,
  active,
  onPress,
}: {
  icon: any;
  label: string;
  badge?: number;
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
      <Ionicons
        name={icon}
        size={14}
        color={active ? COLORS.primary : COLORS.textSecondary}
      />
      <Text style={[styles.dropdownBtnText, active && { color: COLORS.primary }]} numberOfLines={1}>
        {label}
      </Text>
      {typeof badge === "number" && badge > 1 ? (
        <View style={styles.dropdownBadge}>
          <Text style={styles.dropdownBadgeText}>{badge}</Text>
        </View>
      ) : null}
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
  multi,
  onPress,
}: {
  label: string;
  emoji?: string;
  count?: number;
  selected?: boolean;
  multi?: boolean;
  onPress: () => void;
}) {
  const iconName = multi
    ? selected
      ? "checkbox"
      : "square-outline"
    : selected
      ? "checkmark-circle"
      : "ellipse-outline";
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
        name={iconName as any}
        size={22}
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
    flex: 1,
  },
  sheetSub: {
    color: COLORS.textMuted,
    fontSize: 12,
    textAlign: "right",
    paddingHorizontal: 6,
    paddingBottom: 8,
  },
  sheetClearText: {
    color: COLORS.primary,
    fontSize: 13,
    fontWeight: "800",
  },
  applyBtn: {
    backgroundColor: COLORS.primary,
    paddingVertical: 14,
    marginHorizontal: 0,
    marginBottom: 10,
    borderRadius: RADIUS.pill,
    alignItems: "center",
  },
  applyBtnText: {
    color: "#fff",
    fontWeight: "900",
    fontSize: 14,
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
