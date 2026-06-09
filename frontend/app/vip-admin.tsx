'use client';

import React, { useCallback, useEffect, useState } from "react";
import {
  View, Text, StyleSheet, Pressable, ScrollView, TextInput, ActivityIndicator,
  RefreshControl, Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "../theme";
import { vipApi, type VIPMember } from "../api";
import { loadAuth, clearAuth } from "../utils/auth-storage";

type Status = "all" | "active" | "inactive";

function formatDateShort(iso?: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso + (iso.length === 10 ? "T00:00:00Z" : ""));
    if (isNaN(d.getTime())) return iso;
    const dd = String(d.getUTCDate()).padStart(2, "0");
    const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
    const yy = String(d.getUTCFullYear());
    return `${dd}/${mm}/${yy}`;
  } catch {
    return iso || "—";
  }
}

function formatDateTime(iso?: string | null): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yy = String(d.getFullYear());
    const hh = String(d.getHours()).padStart(2, "0");
    const mn = String(d.getMinutes()).padStart(2, "0");
    return `${dd}/${mm}/${yy} ${hh}:${mn}`;
  } catch {
    return iso || "—";
  }
}

export default function VIPAdmin() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<VIPMember | null>(null);

  const [members, setMembers] = useState<VIPMember[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<{ total: number; active: number; inactive: number; new_this_week: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Status>("all");

  // Boot: load token, check is_admin, kick out otherwise
  useEffect(() => {
    (async () => {
      const auth = await loadAuth();
      if (!auth.token || !auth.member) {
        router.replace("/vip-login");
        return;
      }
      if (!auth.member.is_admin) {
        Alert.alert("אין הרשאות", "הדף הזה זמין רק למנהלים.");
        router.replace("/vip");
        return;
      }
      setToken(auth.token);
      setMe(auth.member);
    })();
  }, [router]);

  const fetchAll = useCallback(async (tk: string, q: string, st: Status) => {
    const [list, s] = await Promise.all([
      vipApi.adminListMembers(tk, { q, status: st, limit: 300 }),
      vipApi.adminStats(tk).catch(() => null),
    ]);
    setMembers(list.items);
    setTotal(list.total);
    if (s) setStats(s);
  }, []);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    fetchAll(token, query, status)
      .catch((e) => console.warn("admin fetch failed", e))
      .finally(() => setLoading(false));
  }, [token, status, fetchAll]); // intentionally omit `query` — debounced manually below

  // Debounced search
  useEffect(() => {
    if (!token) return;
    const t = setTimeout(() => {
      fetchAll(token, query, status).catch(() => {});
    }, 350);
    return () => clearTimeout(t);
  }, [query, token, status, fetchAll]);

  const onRefresh = useCallback(async () => {
    if (!token) return;
    setRefreshing(true);
    try {
      await fetchAll(token, query, status);
    } finally {
      setRefreshing(false);
    }
  }, [token, query, status, fetchAll]);

  const logout = async () => {
    await clearAuth();
    router.replace("/vip");
  };

  const onToggle = async (m: VIPMember) => {
    if (!token) return;
    if (m.is_admin) {
      Alert.alert("פעולה לא אפשרית", "אי אפשר להשבית חשבון מנהל.");
      return;
    }
    const goingInactive = m.is_active;
    const verb = goingInactive ? "להשבית" : "להפעיל";
    const confirmed = await new Promise<boolean>((resolve) => {
      Alert.alert(
        `האם ${verb} את ${m.full_name}?`,
        goingInactive
          ? "המשתמש לא יוכל להתחבר ולהציג את הכרטיס שלו עד שתפעילו אותו מחדש."
          : "המשתמש יוכל שוב להתחבר ולהשתמש בכרטיס.",
        [
          { text: "ביטול", style: "cancel", onPress: () => resolve(false) },
          { text: verb, style: goingInactive ? "destructive" : "default", onPress: () => resolve(true) },
        ]
      );
    });
    if (!confirmed) return;

    setBusyId(m.id);
    try {
      const res = await vipApi.adminToggleActive(token, m.id);
      setMembers((prev) => prev.map((x) => (x.id === m.id ? res.member : x)));
      if (stats) {
        setStats({
          ...stats,
          active: stats.active + (res.member.is_active ? 1 : -1),
          inactive: stats.inactive + (res.member.is_active ? -1 : 1),
        });
      }
    } catch (e: any) {
      Alert.alert("שגיאה", e?.message || "לא הצלחנו לעדכן את החבר");
    } finally {
      setBusyId(null);
    }
  };

  const StatusPill = ({ active }: { active: boolean }) => (
    <View style={[styles.statusPill, active ? styles.statusActive : styles.statusInactive]}>
      <View style={[styles.statusDot, { backgroundColor: active ? "#16A34A" : "#9CA3AF" }]} />
      <Text style={[styles.statusText, { color: active ? "#15803D" : "#64748B" }]}>
        {active ? "פעיל" : "לא פעיל"}
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={({ pressed }) => [styles.iconBtn, pressed && { opacity: 0.5 }]} testID="admin-back">
          <Ionicons name="chevron-forward" size={22} color={COLORS.textPrimary} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.headerTitle}>פאנל ניהול</Text>
          <Text style={styles.headerSub}>VIP — חברי המועדון</Text>
        </View>
        <Pressable onPress={logout} style={({ pressed }) => [styles.iconBtn, pressed && { opacity: 0.5 }]} testID="admin-logout">
          <Ionicons name="log-out-outline" size={20} color={COLORS.textSecondary} />
        </Pressable>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        {/* Stats cards */}
        <View style={styles.statsRow}>
          <View style={styles.statBox}>
            <Text style={styles.statNumber}>{stats?.total ?? "—"}</Text>
            <Text style={styles.statLabel}>חברים</Text>
          </View>
          <View style={[styles.statBox, { backgroundColor: "#DCFCE7" }]}>
            <Text style={[styles.statNumber, { color: "#15803D" }]}>{stats?.active ?? "—"}</Text>
            <Text style={[styles.statLabel, { color: "#15803D" }]}>פעילים</Text>
          </View>
          <View style={[styles.statBox, { backgroundColor: "#FEF3C7" }]}>
            <Text style={[styles.statNumber, { color: "#92400E" }]}>{stats?.new_this_week ?? "—"}</Text>
            <Text style={[styles.statLabel, { color: "#92400E" }]}>חדשים השבוע</Text>
          </View>
          <View style={[styles.statBox, { backgroundColor: "#FEE2E2" }]}>
            <Text style={[styles.statNumber, { color: "#991B1B" }]}>{stats?.inactive ?? "—"}</Text>
            <Text style={[styles.statLabel, { color: "#991B1B" }]}>לא פעילים</Text>
          </View>
        </View>

        {/* Search */}
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={COLORS.textMuted} />
          <TextInput
            placeholder="חיפוש לפי שם, טלפון, מייל או מספר חבר..."
            placeholderTextColor={COLORS.textMuted}
            style={styles.searchInput}
            value={query}
            onChangeText={setQuery}
            autoCorrect={false}
            returnKeyType="search"
            textAlign="right"
            testID="admin-search"
          />
          {query.length > 0 ? (
            <Pressable onPress={() => setQuery("")} style={({ pressed }) => [pressed && { opacity: 0.5 }]}>
              <Ionicons name="close-circle" size={18} color={COLORS.textMuted} />
            </Pressable>
          ) : null}
        </View>

        {/* Filter chips */}
        <View style={styles.filterRow}>
          {(["all", "active", "inactive"] as Status[]).map((s) => (
            <Pressable
              key={s}
              onPress={() => setStatus(s)}
              style={({ pressed }) => [
                styles.chip,
                status === s && styles.chipActive,
                pressed && { opacity: 0.7 },
              ]}
              testID={`admin-filter-${s}`}
            >
              <Text style={[styles.chipText, status === s && styles.chipTextActive]}>
                {s === "all" ? "הכל" : s === "active" ? "פעילים" : "לא פעילים"}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={styles.resultsCount}>סה״כ {total} חברים</Text>

        {/* List */}
        {loading ? (
          <ActivityIndicator color={COLORS.primary} size="large" style={{ marginTop: 30 }} />
        ) : members.length === 0 ? (
          <Text style={styles.empty}>לא נמצאו חברים</Text>
        ) : (
          members.map((m) => (
            <View key={m.id} style={[styles.memberCard, !m.is_active && styles.memberCardInactive]} testID={`admin-member-${m.id}`}>
              <View style={styles.memberHead}>
                <View style={{ flex: 1 }}>
                  <View style={styles.nameLine}>
                    <Text style={styles.memberName} numberOfLines={1}>{m.full_name}</Text>
                    {m.is_admin ? (
                      <View style={styles.adminBadge}>
                        <Ionicons name="shield-checkmark" size={11} color="#fff" />
                        <Text style={styles.adminBadgeText}>מנהל</Text>
                      </View>
                    ) : null}
                  </View>
                  <Text style={styles.memberNumber}>{m.member_number}</Text>
                </View>
                <StatusPill active={m.is_active} />
              </View>

              <View style={styles.detailGrid}>
                <Detail label="טלפון" value={m.phone} icon="call-outline" />
                <Detail label="מייל" value={m.email} icon="mail-outline" />
                <Detail label="תאריך לידה" value={formatDateShort(m.dob)} icon="calendar-outline" />
                <Detail label="כתובת" value={m.address} icon="home-outline" wide />
                <Detail label="הצטרפות" value={formatDateShort(m.join_date)} icon="enter-outline" />
                <Detail label="תוקף עד" value={formatDateShort(m.expiry_date)} icon="time-outline" />
                <Detail label="כניסה אחרונה" value={formatDateTime(m.last_login)} icon="log-in-outline" wide />
              </View>

              {!m.is_admin ? (
                <Pressable
                  onPress={() => onToggle(m)}
                  disabled={busyId === m.id}
                  style={({ pressed }) => [
                    styles.toggleBtn,
                    m.is_active ? styles.toggleDanger : styles.toggleSuccess,
                    pressed && { opacity: 0.7 },
                    busyId === m.id && { opacity: 0.5 },
                  ]}
                  testID={`admin-toggle-${m.id}`}
                >
                  {busyId === m.id ? (
                    <ActivityIndicator color="#fff" size="small" />
                  ) : (
                    <>
                      <Ionicons
                        name={m.is_active ? "lock-closed-outline" : "checkmark-circle-outline"}
                        size={16}
                        color="#fff"
                      />
                      <Text style={styles.toggleText}>{m.is_active ? "השבת" : "הפעל מחדש"}</Text>
                    </>
                  )}
                </Pressable>
              ) : null}
            </View>
          ))
        )}

        <View style={{ height: 30 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Detail({
  label, value, icon, wide,
}: { label: string; value: string; icon: any; wide?: boolean }) {
  return (
    <View style={[styles.detailCell, wide && { flexBasis: "100%" }]}>
      <View style={styles.detailLabelLine}>
        <Ionicons name={icon} size={12} color={COLORS.textMuted} />
        <Text style={styles.detailLabel}>{label}</Text>
      </View>
      <Text style={styles.detailValue} numberOfLines={wide ? 2 : 1}>{value || "—"}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.background },
  header: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingTop: 6,
    paddingBottom: 12,
    backgroundColor: COLORS.background,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  headerTitle: { fontSize: 18, fontWeight: "900", color: COLORS.textPrimary, textAlign: "right" },
  headerSub: { fontSize: 12, color: COLORS.textMuted, textAlign: "right" },
  iconBtn: {
    width: 38, height: 38, borderRadius: 19,
    alignItems: "center", justifyContent: "center",
    backgroundColor: COLORS.card, borderWidth: 1, borderColor: COLORS.border,
  },
  scroll: { padding: 16, paddingBottom: 60 },

  // Stats row
  statsRow: { flexDirection: "row-reverse", gap: 8, marginBottom: 14 },
  statBox: {
    flex: 1,
    backgroundColor: "#E0E7FF",
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 64,
  },
  statNumber: { fontSize: 20, fontWeight: "900", color: "#3730A3" },
  statLabel: { fontSize: 10, fontWeight: "700", color: "#3730A3", marginTop: 2, textAlign: "center" },

  // Search
  searchBox: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: COLORS.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: COLORS.border,
    paddingHorizontal: 14,
    paddingVertical: 10,
    gap: 8,
  },
  searchInput: {
    flex: 1, color: COLORS.textPrimary, fontSize: 14, padding: 0,
  },

  // Filter chips
  filterRow: { flexDirection: "row-reverse", gap: 8, marginTop: 12 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  chipActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  chipText: { fontSize: 12, color: COLORS.textSecondary, fontWeight: "700" },
  chipTextActive: { color: "#fff" },

  resultsCount: {
    marginTop: 14, marginBottom: 10,
    fontSize: 12, fontWeight: "700",
    color: COLORS.textMuted, textAlign: "right",
  },

  empty: { textAlign: "center", color: COLORS.textMuted, marginTop: 40, fontSize: 14 },

  // Member card
  memberCard: {
    backgroundColor: COLORS.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
    padding: 14,
    marginBottom: 10,
  },
  memberCardInactive: {
    backgroundColor: "#F8F9FB",
    borderColor: "#E2E8F0",
    opacity: 0.92,
  },
  memberHead: {
    flexDirection: "row-reverse",
    alignItems: "flex-start",
    gap: 8,
    marginBottom: 10,
  },
  nameLine: { flexDirection: "row-reverse", alignItems: "center", gap: 6 },
  memberName: { fontSize: 16, fontWeight: "900", color: COLORS.textPrimary, textAlign: "right" },
  memberNumber: { fontSize: 11, color: COLORS.textMuted, marginTop: 2, fontWeight: "700", textAlign: "right" },

  adminBadge: {
    flexDirection: "row-reverse", alignItems: "center", gap: 3,
    backgroundColor: COLORS.primary,
    paddingHorizontal: 7, paddingVertical: 2, borderRadius: 999,
  },
  adminBadgeText: { color: "#fff", fontSize: 10, fontWeight: "800" },

  statusPill: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 9, paddingVertical: 4,
    borderRadius: 999,
  },
  statusActive: { backgroundColor: "#DCFCE7" },
  statusInactive: { backgroundColor: "#F1F5F9" },
  statusDot: { width: 6, height: 6, borderRadius: 3 },
  statusText: { fontSize: 11, fontWeight: "800" },

  detailGrid: {
    flexDirection: "row-reverse", flexWrap: "wrap",
    gap: 6,
    marginTop: 4,
  },
  detailCell: {
    flexBasis: "48%", flexGrow: 1,
    backgroundColor: "#F8FAFC",
    borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 6,
    borderWidth: 1, borderColor: "#E2E8F0",
  },
  detailLabelLine: { flexDirection: "row-reverse", alignItems: "center", gap: 4 },
  detailLabel: { color: COLORS.textMuted, fontSize: 10, fontWeight: "700", textAlign: "right" },
  detailValue: { color: COLORS.textPrimary, fontSize: 12, fontWeight: "700", textAlign: "right", marginTop: 2 },

  toggleBtn: {
    marginTop: 10,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 10,
    borderRadius: 10,
  },
  toggleDanger: { backgroundColor: "#DC2626" },
  toggleSuccess: { backgroundColor: "#16A34A" },
  toggleText: { color: "#fff", fontSize: 13, fontWeight: "800" },
});
