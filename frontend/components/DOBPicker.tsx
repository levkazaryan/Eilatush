'use client';

import React, { useState, useRef } from "react";
import {
  View, Text, Pressable, StyleSheet, Modal, Platform, TouchableOpacity,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import DateTimePicker from "@react-native-community/datetimepicker";
import { COLORS } from "../theme";

type Props = {
  label: string;
  value: string; // ISO date string YYYY-MM-DD, or "" if empty
  onChange: (iso: string) => void;
  testID?: string;
  placeholder?: string;
  minimumDate?: Date;
  maximumDate?: Date;
};

// Display helper — pretty Hebrew-style DD/MM/YYYY for visible state
function formatDDMMYYYY(iso: string): string {
  if (!iso) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return "";
  return `${m[3]}/${m[2]}/${m[1]}`;
}

// Convert a JS Date into ISO yyyy-MM-dd (UTC-safe by using local Y/M/D)
function dateToIso(d: Date): string {
  const yy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yy}-${mm}-${dd}`;
}

const DEFAULT_MIN = new Date(1900, 0, 1);
const DEFAULT_MAX = new Date(); // today (no future DOB)

export default function DOBPicker({
  label,
  value,
  onChange,
  testID,
  placeholder = "בחרו תאריך",
  minimumDate = DEFAULT_MIN,
  maximumDate = DEFAULT_MAX,
}: Props) {
  // Native-only modal state
  const [open, setOpen] = useState(false);
  const [tempDate, setTempDate] = useState<Date>(() => {
    if (value) {
      const d = new Date(value + "T00:00:00");
      if (!isNaN(d.getTime())) return d;
    }
    // Default: 25 years ago — typical adult signing up
    const fallback = new Date();
    fallback.setFullYear(fallback.getFullYear() - 25);
    return fallback;
  });

  // ───────── WEB: native browser date picker via hidden <input type="date"> ─────────
  const inputRef = useRef<any>(null);
  const isWeb = Platform.OS === "web";

  const onWebPress = () => {
    if (inputRef.current) {
      // showPicker() is the modern API (Chrome / Safari); fall back to focus + click
      try {
        if (typeof inputRef.current.showPicker === "function") {
          inputRef.current.showPicker();
          return;
        }
      } catch (_) {}
      inputRef.current.focus?.();
      inputRef.current.click?.();
    }
  };

  const onWebChange = (e: any) => {
    const v = e?.target?.value || e?.nativeEvent?.text || "";
    if (v && /^\d{4}-\d{2}-\d{2}$/.test(v)) {
      onChange(v);
    } else if (!v) {
      onChange("");
    }
  };

  // ───────── NATIVE: Modal with DateTimePicker (spinner on iOS, calendar on Android) ─────────
  const openNative = () => {
    if (value) {
      const d = new Date(value + "T00:00:00");
      if (!isNaN(d.getTime())) setTempDate(d);
    } else {
      const fb = new Date();
      fb.setFullYear(fb.getFullYear() - 25);
      setTempDate(fb);
    }
    setOpen(true);
  };

  const onNativeChange = (_: any, date?: Date) => {
    // On Android, the dialog dismisses itself; on iOS we keep the modal open until "Confirm"
    if (date) setTempDate(date);
    if (Platform.OS === "android") {
      setOpen(false);
      if (date) onChange(dateToIso(date));
    }
  };

  const confirmNative = () => {
    onChange(dateToIso(tempDate));
    setOpen(false);
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>{label}</Text>

      <Pressable
        onPress={isWeb ? onWebPress : openNative}
        style={({ pressed }) => [styles.pressable, pressed && { opacity: 0.85 }]}
        testID={testID}
      >
        <Text style={[styles.valueText, !value && styles.placeholderText]} numberOfLines={1}>
          {value ? formatDDMMYYYY(value) : placeholder}
        </Text>
        <Ionicons name="calendar-outline" size={18} color={COLORS.textMuted} />
      </Pressable>

      {/* WEB: hidden native input that opens the browser's date picker */}
      {isWeb ? (
        // @ts-ignore — react-native-web renders these but TS doesn't know about DOM input types
        <input
          ref={inputRef}
          type="date"
          value={value || ""}
          onChange={onWebChange}
          min={dateToIso(minimumDate)}
          max={dateToIso(maximumDate)}
          style={{
            position: "absolute",
            left: -9999,
            top: -9999,
            width: 1,
            height: 1,
            opacity: 0,
            border: 0,
            padding: 0,
            margin: 0,
          }}
          aria-hidden={false}
          tabIndex={-1}
        />
      ) : null}

      {/* NATIVE: Modal with picker */}
      {!isWeb ? (
        <Modal
          visible={open}
          transparent
          animationType="fade"
          onRequestClose={() => setOpen(false)}
        >
          <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
            {/* stopPropagation: pressing the sheet shouldn't dismiss */}
            <Pressable style={styles.sheet} onPress={() => {}}>
              <Text style={styles.sheetTitle}>{label}</Text>
              <DateTimePicker
                value={tempDate}
                mode="date"
                display={Platform.OS === "ios" ? "spinner" : "calendar"}
                minimumDate={minimumDate}
                maximumDate={maximumDate}
                onChange={onNativeChange}
                themeVariant="light"
                style={{ alignSelf: "stretch" }}
              />
              {Platform.OS === "ios" ? (
                <View style={styles.btnRow}>
                  <TouchableOpacity onPress={() => setOpen(false)} style={[styles.btn, styles.btnCancel]}>
                    <Text style={styles.btnCancelText}>ביטול</Text>
                  </TouchableOpacity>
                  <TouchableOpacity onPress={confirmNative} style={[styles.btn, styles.btnConfirm]}>
                    <Text style={styles.btnConfirmText}>אישור</Text>
                  </TouchableOpacity>
                </View>
              ) : null}
            </Pressable>
          </Pressable>
        </Modal>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginBottom: 12, position: "relative" },
  label: {
    fontSize: 13,
    color: COLORS.textSecondary,
    fontWeight: "700",
    marginBottom: 6,
    textAlign: "right",
  },
  pressable: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
    minHeight: 48,
    gap: 10,
  },
  valueText: {
    flex: 1,
    color: COLORS.textPrimary,
    fontSize: 15,
    fontWeight: "600",
    textAlign: "right",
  },
  placeholderText: {
    color: COLORS.textMuted,
    fontWeight: "500",
  },

  // Native modal
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingTop: 18,
    paddingHorizontal: 18,
    paddingBottom: 28,
  },
  sheetTitle: {
    fontSize: 16,
    fontWeight: "900",
    color: COLORS.textPrimary,
    textAlign: "right",
    marginBottom: 8,
  },
  btnRow: {
    flexDirection: "row-reverse",
    gap: 10,
    marginTop: 14,
  },
  btn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  btnConfirm: { backgroundColor: COLORS.primary },
  btnConfirmText: { color: "#fff", fontSize: 15, fontWeight: "800" },
  btnCancel: { backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border },
  btnCancelText: { color: COLORS.textSecondary, fontSize: 15, fontWeight: "700" },
});
