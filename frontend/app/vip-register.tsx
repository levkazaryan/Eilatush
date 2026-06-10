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
import DOBPicker from "../components/DOBPicker";

function toIsoDate(d: string): string | null {
  // Accepts DD/MM/YYYY or YYYY-MM-DD
  const s = d.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const m = s.match(/^(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{4})$/);
  if (m) {
    const dd = m[1].padStart(2, "0");
    const mm = m[2].padStart(2, "0");
    const yy = m[3];
    return `${yy}-${mm}-${dd}`;
  }
  return null;
}

export default function VIPRegisterScreen() {
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [dob, setDob] = useState("");
  const [address, setAddress] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const handleSubmit = async () => {
    setErr(null);
    if (!fullName.trim()) return setErr("הכניסו שם מלא");
    if (!email.trim() || !email.includes("@")) return setErr("כתובת אימייל לא תקינה");
    if (!phone.trim()) return setErr("הכניסו מספר טלפון");
    if (!dob || !/^\d{4}-\d{2}-\d{2}$/.test(dob)) return setErr("בחרו תאריך לידה");
    if (!address.trim()) return setErr("הכניסו כתובת");

    setBusy(true);
    try {
      await register({
        full_name: fullName.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        dob: dob,
        address: address.trim(),
      });
      router.replace("/(tabs)/vip");
    } catch (e: any) {
      const msg = e?.message || "רישום נכשל. נסו שוב.";
      setErr(msg);
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
          <Text style={styles.headerTitle}>הצטרפות למועדון</Text>
          <View style={{ width: 40 }} />
        </View>

        <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
          <Text style={styles.intro}>מילוי קצר — והכרטיס שלכם מוכן {"\u00B7"} ללא עלות וללא מחויבות</Text>

          <Field label="שם מלא" value={fullName} onChange={setFullName} placeholder="לדוגמה: דניאל לוי" autoCapitalize="words" testID="vip-name" />
          <Field label="אימייל" value={email} onChange={setEmail} placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" testID="vip-email" />
          <Field label="טלפון (ישראלי)" value={phone} onChange={setPhone} placeholder="050-1234567" keyboardType="phone-pad" testID="vip-phone" />
          <DOBPicker label="תאריך לידה" value={dob} onChange={setDob} testID="vip-dob" />
          <Field label="כתובת באילת" value={address} onChange={setAddress} placeholder="לדוגמה: התמרים 7, אילת" testID="vip-address" />

          {err ? <Text style={styles.errText}>{err}</Text> : null}

          <Pressable
            onPress={handleSubmit}
            disabled={busy}
            style={({ pressed }) => [styles.submit, busy && { opacity: 0.6 }, pressed && { opacity: 0.8 }]}
            testID="vip-register-submit"
          >
            {busy ? (
              <ActivityIndicator color="#000" />
            ) : (
              <>
                <Ionicons name="sparkles" size={18} color="#000" />
                <Text style={styles.submitText}>קבלו את הכרטיס</Text>
              </>
            )}
          </Pressable>

          <Pressable onPress={() => router.replace("/vip-login")} style={styles.altLink}>
            <Text style={styles.altLinkText}>כבר רשום? <Text style={{ color: COLORS.primary, fontWeight: "800" }}>התחבר</Text></Text>
          </Pressable>

          <Text style={styles.legal}>בלחיצה על הכפתור אני מאשר/ת שהפרטים נכונים ומסכים לשמירתם במערכת אילתוש לצורך תפעול הכרטיס.</Text>
          <View style={{ height: 40 }} />
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Field(props: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  keyboardType?: any;
  autoCapitalize?: any;
  testID?: string;
}) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.fieldLabel}>{props.label}</Text>
      <TextInput
        value={props.value}
        onChangeText={props.onChange}
        placeholder={props.placeholder}
        placeholderTextColor={COLORS.textMuted}
        keyboardType={props.keyboardType}
        autoCapitalize={props.autoCapitalize || "none"}
        style={styles.input}
        testID={props.testID}
      />
    </View>
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
  scroll: { padding: SPACING.md },
  intro: { fontSize: 14, color: COLORS.textSecondary, textAlign: "center", marginBottom: 18 },
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
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 6,
  },
  submitText: { color: "#000", fontSize: 16, fontWeight: "900" },
  errText: { color: COLORS.danger, fontSize: 13, marginBottom: 10, textAlign: "center" },
  altLink: { marginTop: 14, alignItems: "center" },
  altLinkText: { color: COLORS.textSecondary, fontSize: 14 },
  legal: { fontSize: 11, color: COLORS.textMuted, marginTop: 22, textAlign: "center", lineHeight: 16 },
});
