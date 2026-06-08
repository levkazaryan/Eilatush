'use client';

import React, { useState } from "react";
import {
  View, Text, StyleSheet, ScrollView, TextInput, Pressable, ActivityIndicator,
  KeyboardAvoidingView, Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { COLORS, RADIUS, SPACING } from "../theme";
import { useAuth } from "../utils/auth-context";

function toIsoDate(d: string): string | null {
  const s = d.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const m = s.match(/^(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{4})$/);
  if (m) {
    const dd = m[1].padStart(2, "0");
    const mm = m[2].padStart(2, "0");
    return `${m[3]}-${mm}-${dd}`;
  }
  return null;
}

export default function VIPLoginScreen() {
  const { login } = useAuth();
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async () => {
    setErr(null);
    if (!phone.trim()) return setErr("הכניסו מספר טלפון");
    const dobIso = toIsoDate(dob);
    if (!dobIso) return setErr("תאריך לידה בפורמט DD/MM/YYYY");
    setBusy(true);
    try {
      await login({ phone: phone.trim(), dob: dobIso });
      router.replace("/(tabs)/vip");
    } catch (e: any) {
      setErr(e?.message || "התחברות נכשלה");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn} accessibilityLabel="חזור">
            <Ionicons name="chevron-forward" size={22} color={COLORS.textPrimary} />
          </Pressable>
          <Text style={styles.headerTitle}>התחברות לכרטיס</Text>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <View style={styles.intro}>
            <Ionicons name="diamond" size={42} color="#D4AF37" />
            <Text style={styles.introText}>יש לך כבר כרטיס תושב אילת VIP?\nהתחברו עם הטלפון ותאריך הלידה שלכם</Text>
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>טלפון</Text>
            <TextInput
              value={phone}
              onChangeText={setPhone}
              placeholder="050-1234567"
              placeholderTextColor={COLORS.textMuted}
              keyboardType="phone-pad"
              style={styles.input}
              testID="vip-login-phone"
            />
          </View>

          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>תאריך לידה (DD/MM/YYYY)</Text>
            <TextInput
              value={dob}
              onChangeText={setDob}
              placeholder="15/05/1990"
              placeholderTextColor={COLORS.textMuted}
              keyboardType="numbers-and-punctuation"
              style={styles.input}
              testID="vip-login-dob"
            />
          </View>

          {err ? <Text style={styles.errText}>{err}</Text> : null}

          <Pressable
            onPress={handleSubmit}
            disabled={busy}
            style={({ pressed }) => [styles.submit, busy && { opacity: 0.6 }, pressed && { opacity: 0.8 }]}
            testID="vip-login-submit"
          >
            {busy ? (
              <ActivityIndicator color="#000" />
            ) : (
              <Text style={styles.submitText}>התחברות</Text>
            )}
          </Pressable>

          <Pressable onPress={() => router.replace("/vip-register")} style={styles.altLink}>
            <Text style={styles.altLinkText}>אין לך עדיין כרטיס? <Text style={{ color: COLORS.primary, fontWeight: "800" }}>הצטרפות</Text></Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.sm,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: COLORS.surface,
  },
  backBtn: {
    width: 40, height: 40, borderRadius: 20,
    alignItems: "center", justifyContent: "center",
    backgroundColor: COLORS.cardHigh,
  },
  headerTitle: { flex: 1, fontSize: 18, fontWeight: "900", color: COLORS.textPrimary, textAlign: "center" },
  scroll: { padding: SPACING.md, paddingTop: 30 },
  intro: { alignItems: "center", marginBottom: 24, gap: 10 },
  introText: { fontSize: 14, color: COLORS.textSecondary, textAlign: "center", lineHeight: 21 },
  fieldGroup: { marginBottom: 14 },
  fieldLabel: { fontSize: 13, fontWeight: "800", color: COLORS.textPrimary, marginBottom: 6, textAlign: "right" },
  input: {
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: RADIUS.md,
    paddingHorizontal: 14,
    paddingVertical: Platform.OS === "ios" ? 14 : 10,
    fontSize: 15,
    color: COLORS.textPrimary,
    textAlign: "right",
    writingDirection: "rtl",
    minHeight: 46,
    ...({ outlineStyle: "none" } as any),
  },
  submit: {
    backgroundColor: "#D4AF37",
    borderRadius: RADIUS.pill,
    paddingVertical: 15,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 6,
  },
  submitText: { color: "#000", fontSize: 16, fontWeight: "900" },
  errText: { color: COLORS.danger, fontSize: 13, marginBottom: 10, textAlign: "center" },
  altLink: { marginTop: 18, alignItems: "center" },
  altLinkText: { color: COLORS.textSecondary, fontSize: 14 },
});
