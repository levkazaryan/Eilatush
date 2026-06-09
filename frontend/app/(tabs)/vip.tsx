'use client';

import React, { useCallback, useEffect, useState } from "react";
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator, RefreshControl, Platform } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { router, useFocusEffect } from "expo-router";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { useAuth } from "../../utils/auth-context";
import { vipApi, type VIPDiscount } from "../../api";
import VIPCard from "../../components/VIPCard";
import DiscountCard from "../../components/DiscountCard";
import { trackScreen } from "../../utils/analytics";

export default function VIPTabScreen() {
  const { hydrated, member, token, logout, refreshMember } = useAuth();
  const [discounts, setDiscounts] = useState<VIPDiscount[] | null>(null);
  const [teaserCount, setTeaserCount] = useState<number>(8);
  const [loadingDiscounts, setLoadingDiscounts] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    trackScreen("vip");
    vipApi.teaser().then((t) => setTeaserCount(t.discount_count)).catch(() => {});
  }, []);

  const loadDiscounts = useCallback(async () => {
    if (!token) return;
    setLoadingDiscounts(true);
    try {
      const list = await vipApi.discounts(token);
      setDiscounts(list);
    } catch (e) {
      console.warn("discounts load failed", e);
      setDiscounts([]);
    } finally {
      setLoadingDiscounts(false);
    }
  }, [token]);

  useFocusEffect(
    useCallback(() => {
      if (token) {
        loadDiscounts();
        refreshMember();
      }
    }, [token, loadDiscounts, refreshMember])
  );

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      if (token) {
        await Promise.all([loadDiscounts(), refreshMember()]);
      } else {
        await vipApi.teaser().then((t) => setTeaserCount(t.discount_count)).catch(() => {});
      }
    } finally {
      setRefreshing(false);
    }
  }, [token, loadDiscounts, refreshMember]);

  // -------- LOADING (hydrating from storage) --------
  if (!hydrated) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <View style={styles.center}>
          <ActivityIndicator color={COLORS.primary} size="large" />
        </View>
      </SafeAreaView>
    );
  }

  // -------- LOGGED-OUT (preview + CTA) --------
  if (!member) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
        >
          <View style={styles.previewHeader}>
            <Text style={styles.eyebrow}>המועדון לתושבי אילת</Text>
            <Text style={styles.h1}>תושב אילת <Text style={{ color: "#D4AF37" }}>VIP</Text></Text>
            <View style={styles.headerUnderline} />
          </View>

          <View style={styles.cardStage}>
            <View style={styles.cardWrap}>
              <VIPCard preview interactive />
            </View>
          </View>

          <View style={styles.benefitsBox}>
            <Text style={styles.benefitsTitle}>למה זה שווה?</Text>
            <Text style={styles.benefitsText}>
              כרטיס ה-VIP הראשון של תושבי אילת — הטבות בלעדיות אצל העסקים האהובים עליכם, ובקרוב גם מחוץ לעיר.{"\n\n"}מתנות והנחות במסעדות, בתי קפה, חנויות, אטרקציות ועוד — בלי הגרלות ובלי תנאים מסובכים.
            </Text>
            <View style={styles.bulletsRow}>
              <View style={styles.bullet}>
                <Text style={styles.bulletNum}>🎁</Text>
                <Text style={styles.bulletText}>{teaserCount} הטבות {"\n"}מחכות לכם</Text>
              </View>
              <View style={styles.bullet}>
                <Text style={styles.bulletNum}>🆕</Text>
                <Text style={styles.bulletText}>כל שבוע {"\n"}מתווספות חדשות</Text>
              </View>
              <View style={styles.bullet}>
                <Text style={styles.bulletNum}>🌍</Text>
                <Text style={styles.bulletText}>גם מחוץ לאילת {"\n"}<Text style={{ color: COLORS.textMuted, fontWeight: "600" }}>(בקרוב)</Text></Text>
              </View>
            </View>
          </View>

          <View style={styles.freeBox}>
            <Text style={styles.freeBoxTitle}>חצי שנה במתנה — בלי שום עלות</Text>
            <Text style={styles.freeBoxText}>בלי כרטיס אשראי · בלי התחייבות · אפשר לבטל מתי שרוצים</Text>
          </View>

          <Pressable
            onPress={() => router.push("/vip-register")}
            style={({ pressed }) => [styles.ctaBig, pressed && { opacity: 0.85 }]}
            testID="vip-claim-cta"
          >
            <Ionicons name="sparkles" size={20} color="#000" />
            <Text style={styles.ctaBigText}>אני רוצה את הכרטיס שלי — בחינם</Text>
          </Pressable>

          <Pressable
            onPress={() => router.push("/vip-login")}
            style={({ pressed }) => [styles.loginLink, pressed && { opacity: 0.6 }]}
            testID="vip-login-link"
          >
            <Text style={styles.loginLinkText}>כבר יש לכם כרטיס? <Text style={{ color: COLORS.primary, fontWeight: "800" }}>התחברו</Text></Text>
          </Pressable>

          <Text style={styles.disclaimer}>
            הכרטיס תקף רק בעסקים המשתתפים. כדי לממש את ההטבה — פשוט הציגו את הכרטיס בקופה לפני התשלום.
          </Text>
        </ScrollView>
      </SafeAreaView>
    );
  }

  // -------- LOGGED-IN --------
  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <ScrollView
        contentContainerStyle={styles.scroll}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
      >
        <View style={styles.memberHeader}>
          <View style={{ flex: 1 }}>
            <Text style={styles.eyebrow}>שלום, {member.full_name.split(" ")[0]} 👋</Text>
            <Text style={styles.h2}>הכרטיס הדיגיטלי שלכם</Text>
          </View>
          <Pressable
            onPress={logout}
            style={({ pressed }) => [styles.iconBtnGhost, pressed && { opacity: 0.6 }]}
            accessibilityLabel="התנתקות"
            testID="vip-logout"
          >
            <Ionicons name="log-out-outline" size={20} color={COLORS.textSecondary} />
          </Pressable>
        </View>

        <View style={styles.cardStage}>
          <View style={styles.cardWrap}>
            <VIPCard
              fullName={member.full_name}
              dob={member.dob}
              memberNumber={member.member_number}
              expiryDate={member.expiry_date}
            />
          </View>
        </View>

        <View style={styles.discountsHeader}>
          <Text style={styles.discountsTitle}>🎁 ההטבות שלכם</Text>
          <Text style={styles.discountsSub}>כדי לממש — פשוט הציגו את הכרטיס בקופה</Text>
        </View>

        {loadingDiscounts ? (
          <ActivityIndicator color={COLORS.primary} size="small" style={{ marginVertical: 30 }} />
        ) : (discounts || []).length === 0 ? (
          <Text style={styles.empty}>ההטבות יופיעו כאן בקרוב ✌️</Text>
        ) : (
          <View>
            {(discounts || []).map((d) => (
              <DiscountCard key={d.id} item={d} />
            ))}
          </View>
        )}

        <View style={styles.comingSoon}>
          <Text style={styles.comingSoonTitle}>🌍 גם מחוץ לאילת — בקרוב</Text>
          <Text style={styles.comingSoonText}>אנחנו עובדים על זה — בקרוב תוכלו ליהנות מהטבות גם בערים נוספות בארץ 🙏</Text>
        </View>

        <View style={{ height: 120 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  scroll: { padding: SPACING.md, paddingBottom: 32 },

  previewHeader: { alignItems: "flex-end", marginBottom: 14 },
  headerUnderline: {
    height: 1.2,
    width: 60,
    backgroundColor: "#D4AF37",
    opacity: 0.85,
    marginTop: 6,
    alignSelf: "flex-end",
  },
  memberHeader: {
    flexDirection: "row-reverse",
    alignItems: "center",
    marginBottom: 14,
    gap: 10,
  },
  eyebrow: { fontSize: 12, color: COLORS.textMuted, fontWeight: "700", letterSpacing: 0.5, textAlign: "right" },
  h1: { fontSize: 32, fontWeight: "900", color: COLORS.textPrimary, textAlign: "right", marginTop: 4 },
  h2: { fontSize: 22, fontWeight: "900", color: COLORS.textPrimary, textAlign: "right", marginTop: 2 },

  cardStage: {
    marginVertical: 18,
    paddingVertical: 8,
    alignItems: "center",
    justifyContent: "center",
  },
  cardWrap: { width: "100%", maxWidth: 380, alignSelf: "center" },

  benefitsBox: {
    marginTop: 18,
    padding: 16,
    backgroundColor: COLORS.card,
    borderRadius: RADIUS.lg,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  benefitsTitle: { fontSize: 18, fontWeight: "900", color: COLORS.textPrimary, textAlign: "right" },
  benefitsText: { fontSize: 14, color: COLORS.textSecondary, marginTop: 6, lineHeight: 22, textAlign: "right", writingDirection: "rtl" },

  bulletsRow: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: 10,
    marginTop: 14,
  },
  bullet: {
    flexBasis: "30%",
    flexGrow: 1,
    alignItems: "center",
    backgroundColor: "rgba(20,184,179,0.08)",
    paddingVertical: 12,
    paddingHorizontal: 8,
    borderRadius: RADIUS.md,
    borderWidth: 1,
    borderColor: "rgba(20,184,179,0.25)",
  },
  bulletNum: { fontSize: 26 },
  bulletText: { fontSize: 12, color: COLORS.textPrimary, fontWeight: "700", textAlign: "center", marginTop: 4 },

  freeBox: {
    marginTop: 16,
    padding: 14,
    borderRadius: RADIUS.md,
    backgroundColor: "rgba(212,175,55,0.10)",
    borderWidth: 1,
    borderColor: "rgba(212,175,55,0.45)",
    alignItems: "center",
  },
  freeBoxTitle: { fontSize: 16, fontWeight: "900", color: "#8C6B0D" },
  freeBoxText: { fontSize: 12, color: "#8C6B0D", marginTop: 4, fontWeight: "600" },

  ctaBig: {
    marginTop: 18,
    backgroundColor: "#D4AF37",
    borderRadius: RADIUS.pill,
    paddingVertical: 16,
    paddingHorizontal: 24,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    ...Platform.select({
      ios: { shadowColor: "#D4AF37", shadowOpacity: 0.5, shadowRadius: 16, shadowOffset: { width: 0, height: 6 } },
      android: { elevation: 8 },
      default: { boxShadow: "0 6px 18px rgba(212,175,55,0.5)" } as any,
    }),
  },
  ctaBigText: { color: "#000", fontWeight: "900", fontSize: 16 },

  loginLink: { marginTop: 14, alignItems: "center" },
  loginLinkText: { fontSize: 14, color: COLORS.textSecondary, textAlign: "center" },

  disclaimer: { fontSize: 11, color: COLORS.textMuted, marginTop: 22, textAlign: "center", lineHeight: 16 },

  discountsHeader: { marginTop: 6, marginBottom: 10, alignItems: "flex-end" },
  discountsTitle: { fontSize: 18, fontWeight: "900", color: COLORS.textPrimary, textAlign: "right" },
  discountsSub: { fontSize: 12, color: COLORS.textMuted, marginTop: 2, textAlign: "right" },
  empty: { textAlign: "center", color: COLORS.textMuted, padding: 20 },

  comingSoon: {
    marginTop: 18,
    padding: 16,
    borderRadius: RADIUS.lg,
    backgroundColor: COLORS.cardHigh,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderStyle: "dashed",
  },
  comingSoonTitle: { fontSize: 16, fontWeight: "900", color: COLORS.textPrimary, textAlign: "right" },
  comingSoonText: { fontSize: 13, color: COLORS.textSecondary, marginTop: 4, textAlign: "right", writingDirection: "rtl" },

  iconBtnGhost: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
});
