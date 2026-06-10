'use client';

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  View, Text, Pressable, StyleSheet, Modal, ScrollView, Platform,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "../theme";

type Props = {
  label: string;
  value: string; // ISO date YYYY-MM-DD or ""
  onChange: (iso: string) => void;
  testID?: string;
  minimumYear?: number;
  maximumYear?: number;
};

// Hebrew month names (Gregorian calendar — what people use in everyday life)
const HE_MONTHS = [
  "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
  "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
];

function daysInMonth(year: number | null, month: number | null): number {
  if (!year || !month) return 31;
  // month is 1-12
  return new Date(year, month, 0).getDate();
}

function parseIso(iso: string): { d: number | null; m: number | null; y: number | null } {
  const mm = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
  if (!mm) return { d: null, m: null, y: null };
  return { y: Number(mm[1]), m: Number(mm[2]), d: Number(mm[3]) };
}

function buildIso(y: number | null, m: number | null, d: number | null): string {
  if (!y || !m || !d) return "";
  const mm = String(m).padStart(2, "0");
  const dd = String(d).padStart(2, "0");
  return `${y}-${mm}-${dd}`;
}

type FieldKind = "day" | "month" | "year";

export default function DOBPicker({
  label,
  value,
  onChange,
  testID,
  minimumYear = 1900,
  maximumYear = new Date().getFullYear(),
}: Props) {
  const initial = parseIso(value);
  const [day, setDay] = useState<number | null>(initial.d);
  const [month, setMonth] = useState<number | null>(initial.m);
  const [year, setYear] = useState<number | null>(initial.y);
  const [openField, setOpenField] = useState<FieldKind | null>(null);
  const lastEmittedRef = useRef<string>("");

  // Keep internal state in sync if the parent resets/changes the value externally
  useEffect(() => {
    const p = parseIso(value);
    if (p.d !== day || p.m !== month || p.y !== year) {
      setDay(p.d);
      setMonth(p.m);
      setYear(p.y);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Emit only when we have a complete, valid date
  useEffect(() => {
    if (day && month && year) {
      // Clamp day if it exceeds the month length (e.g., February 30 → February 28/29)
      const dim = daysInMonth(year, month);
      const safeDay = Math.min(day, dim);
      const iso = buildIso(year, month, safeDay);
      if (iso !== lastEmittedRef.current && iso !== value) {
        lastEmittedRef.current = iso;
        onChange(iso);
      }
      if (safeDay !== day) setDay(safeDay);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [day, month, year]);

  const days = useMemo(() => Array.from({ length: daysInMonth(year, month) }, (_, i) => i + 1), [year, month]);
  const years = useMemo(() => {
    const arr: number[] = [];
    for (let y = maximumYear; y >= minimumYear; y--) arr.push(y);
    return arr;
  }, [minimumYear, maximumYear]);

  const openTitle = openField === "day" ? "בחרו יום" : openField === "month" ? "בחרו חודש" : "בחרו שנה";
  const openOptions: (number | { label: string; value: number })[] =
    openField === "day"
      ? days
      : openField === "month"
      ? HE_MONTHS.map((nm, idx) => ({ label: nm, value: idx + 1 }))
      : years;

  const openSelected =
    openField === "day" ? day : openField === "month" ? month : openField === "year" ? year : null;

  const selectOption = (val: number) => {
    if (openField === "day") setDay(val);
    else if (openField === "month") setMonth(val);
    else if (openField === "year") setYear(val);
    setOpenField(null);
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>

      {/* Three boxes — RTL natural order: Day | Month | Year (right → left).
          Using flexDirection: row gives Day first on right in RTL context. */}
      <View style={styles.row}>
        <PickerBox
          placeholder="יום"
          value={day != null ? String(day) : ""}
          onPress={() => setOpenField("day")}
          testID={testID ? `${testID}-day` : undefined}
        />
        <PickerBox
          placeholder="חודש"
          value={month != null ? HE_MONTHS[month - 1] : ""}
          onPress={() => setOpenField("month")}
          testID={testID ? `${testID}-month` : undefined}
        />
        <PickerBox
          placeholder="שנה"
          value={year != null ? String(year) : ""}
          onPress={() => setOpenField("year")}
          testID={testID ? `${testID}-year` : undefined}
        />
      </View>

      {/* Selection modal (shared for all 3 fields) */}
      <Modal
        visible={openField !== null}
        transparent
        animationType="slide"
        onRequestClose={() => setOpenField(null)}
      >
        <Pressable style={styles.backdrop} onPress={() => setOpenField(null)}>
          <Pressable style={styles.sheet} onPress={() => {}}>
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetTitle}>{openTitle}</Text>
              <Pressable
                onPress={() => setOpenField(null)}
                style={({ pressed }) => [styles.closeBtn, pressed && { opacity: 0.5 }]}
                hitSlop={8}
              >
                <Ionicons name="close" size={20} color={COLORS.textSecondary} />
              </Pressable>
            </View>
            <ScrollView
              style={styles.list}
              contentContainerStyle={{ paddingVertical: 6 }}
              showsVerticalScrollIndicator
            >
              {openOptions.map((opt, idx) => {
                const isObj = typeof opt === "object";
                const optValue = isObj ? (opt as any).value : (opt as number);
                const optLabel = isObj ? (opt as any).label : String(opt);
                const selected = openSelected === optValue;
                return (
                  <Pressable
                    key={`${optValue}-${idx}`}
                    onPress={() => selectOption(optValue)}
                    style={({ pressed }) => [
                      styles.option,
                      selected && styles.optionSelected,
                      pressed && { opacity: 0.7 },
                    ]}
                    testID={openField ? `dob-opt-${openField}-${optValue}` : undefined}
                  >
                    <Text style={[styles.optionText, selected && styles.optionTextSelected]}>
                      {optLabel}
                    </Text>
                    {selected ? (
                      <Ionicons name="checkmark" size={20} color={COLORS.primary} />
                    ) : null}
                  </Pressable>
                );
              })}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

function PickerBox({
  placeholder,
  value,
  onPress,
  testID,
}: { placeholder: string; value: string; onPress: () => void; testID?: string }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.box, pressed && { opacity: 0.85 }]}
      testID={testID}
    >
      <Text style={[styles.boxValue, !value && styles.boxPlaceholder]} numberOfLines={1}>
        {value || placeholder}
      </Text>
      <Ionicons name="chevron-down" size={14} color={COLORS.textMuted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 12 },
  label: {
    fontSize: 13,
    color: COLORS.textSecondary,
    fontWeight: "700",
    marginBottom: 6,
    textAlign: "right",
  },
  row: {
    flexDirection: "row",
    gap: 8,
  },
  box: {
    flex: 1,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 6,
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 12,
    minHeight: 48,
  },
  boxValue: {
    flex: 1,
    color: COLORS.textPrimary,
    fontSize: 15,
    fontWeight: "700",
    textAlign: "center",
  },
  boxPlaceholder: {
    color: COLORS.textMuted,
    fontWeight: "500",
  },

  // Modal
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 12,
    paddingBottom: Platform.OS === "ios" ? 32 : 18,
    maxHeight: "75%",
  },
  sheetHeader: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 18,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  sheetTitle: {
    fontSize: 17,
    fontWeight: "900",
    color: COLORS.textPrimary,
    textAlign: "right",
  },
  closeBtn: {
    width: 36, height: 36, borderRadius: 18,
    alignItems: "center", justifyContent: "center",
    backgroundColor: "#F1F5F9",
  },
  list: {
    paddingHorizontal: 12,
  },
  option: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 14,
    borderRadius: 12,
    marginVertical: 2,
  },
  optionSelected: {
    backgroundColor: "#FFE5E7", // soft coral tint
  },
  optionText: {
    fontSize: 16,
    color: COLORS.textPrimary,
    fontWeight: "600",
    textAlign: "right",
  },
  optionTextSelected: {
    color: COLORS.primary,
    fontWeight: "900",
  },
});
