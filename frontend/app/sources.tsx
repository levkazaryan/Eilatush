import React from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Pressable,
  Platform,
  Linking,
} from "react-native";
import { Stack, router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { COLORS, RADIUS, SPACING } from "../theme";
import { SafeAreaView } from "react-native-safe-area-context";

/**
 * Data Sources page — lists every external source the app pulls data from,
 * with friendly Hebrew labels and direct URLs.  Mounted at /sources and linked
 * from the Eilatush tab's profile / About menu.
 *
 * This page exists specifically to satisfy Google Play's policy requirement
 * that apps showing governmental information must provide "clear and
 * accessible URL addresses or links to sources (for example, .gov-type
 * domains)."  Government (.gov.il / .muni.il) sources are visually highlighted
 * with a 🏛️ icon and a teal background.
 */

type SrcRow = {
  label: string;
  url: string;
  category: string;
  isGov?: boolean;
};

const SOURCES: SrcRow[] = [
  // ── Government / Municipal ──────────────────────────────────────────────
  { label: "עיריית אילת — מאגר עסקים", url: "https://biz.eilat.muni.il", category: "ממשלתי", isGov: true },
  { label: "עיריית אילת — אתר העירייה", url: "https://www.eilat.muni.il", category: "ממשלתי", isGov: true },
  { label: "עיריית אילת — אירועים (Smarticket)", url: "https://eilatmuni.smarticket.co.il", category: "ממשלתי", isGov: true },

  // ── Local City ──────────────────────────────────────────────────────────
  { label: "Eilat City — אילת סיטי", url: "https://www.eilat.city", category: "מקומי" },

  // ── News ────────────────────────────────────────────────────────────────
  { label: "ynet — חדשות אילת", url: "https://www.ynet.co.il/topics/אילת", category: "חדשות" },
  { label: "ישראל היום — אילת", url: "https://www.israelhayom.co.il", category: "חדשות" },

  // ── Tickets / Events ────────────────────────────────────────────────────
  { label: "סינמה אילת — בתי קולנוע", url: "https://www.cinema-eilat.com", category: "אירועים" },
  { label: "Tickchak — כרטיסים", url: "https://www.tickchak.co.il", category: "אירועים" },
  { label: "Smarticket — כרטיסים", url: "https://www.smarticket.co.il", category: "אירועים" },

  // ── Jobs ────────────────────────────────────────────────────────────────
  { label: "דרושים.co.il", url: "https://www.drushim.co.il", category: "משרות" },
  { label: "JobMaster", url: "https://www.jobmaster.co.il", category: "משרות" },
  { label: "יום-יום", url: "https://www.yomyom.co.il", category: "משרות" },
  { label: "EilatJobs", url: "https://www.eilatjobs.co.il", category: "משרות" },

  // ── Weather ────────────────────────────────────────────────────────────
  { label: "Open-Meteo — מזג אוויר", url: "https://open-meteo.com", category: "מזג אוויר" },
];

const CATEGORY_ORDER = ["ממשלתי", "מקומי", "חדשות", "אירועים", "משרות", "מזג אוויר"];

export default function SourcesScreen() {
  const grouped = React.useMemo(() => {
    const m: Record<string, SrcRow[]> = {};
    for (const s of SOURCES) {
      (m[s.category] ||= []).push(s);
    }
    return m;
  }, []);

  const open = (url: string) => {
    try {
      Linking.openURL(url);
    } catch (e) {
      console.warn("open url failed", e);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.header}>
        <Pressable
          onPress={() => router.back()}
          hitSlop={12}
          style={styles.backBtn}
          android_ripple={{ color: "rgba(0,0,0,0.1)", borderless: true, radius: 22 }}
        >
          <Ionicons name="chevron-forward" size={26} color={COLORS.textPrimary} />
        </Pressable>
        <View style={{ flex: 1 }}>
          <Text style={styles.title}>מקורות מידע</Text>
          <Text style={styles.subtitle}>
            כל הנתונים שמוצגים באפליקציה נשאבים ישירות מהמקורות הרשמיים הבאים
          </Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.notice}>
          <Ionicons name="shield-checkmark" size={20} color={COLORS.secondary} />
          <Text style={styles.noticeText}>
            אילתוש אינו מייצר תוכן חדש — כל המידע (אירועים, עסקים, חדשות, משרות) מסונכרן
            אוטומטית מהמקורות שלהלן. לחיצה על כל מקור פותחת את האתר הרשמי.
          </Text>
        </View>

        {CATEGORY_ORDER.map((cat) => {
          const items = grouped[cat];
          if (!items?.length) return null;
          return (
            <View key={cat} style={styles.section}>
              <Text style={styles.sectionTitle}>{cat}</Text>
              {items.map((s) => (
                <Pressable
                  key={s.url}
                  onPress={() => open(s.url)}
                  style={({ pressed }) => [
                    styles.row,
                    s.isGov && styles.rowGov,
                    pressed && { opacity: 0.7 },
                  ]}
                  android_ripple={{ color: "rgba(0,0,0,0.06)" }}
                >
                  {s.isGov ? <Text style={styles.govEmoji}>🏛️</Text> : (
                    <Ionicons
                      name="link"
                      size={16}
                      color={COLORS.textMuted}
                      style={{ marginEnd: 6 }}
                    />
                  )}
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.rowLabel, s.isGov && styles.rowLabelGov]} numberOfLines={1}>
                      {s.label}
                    </Text>
                    <Text style={styles.rowUrl} numberOfLines={1}>
                      {s.url}
                    </Text>
                  </View>
                  <Ionicons name="open-outline" size={18} color={COLORS.textMuted} />
                </Pressable>
              ))}
            </View>
          );
        })}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: "row-reverse",
    alignItems: "flex-start",
    paddingHorizontal: SPACING.md,
    paddingTop: SPACING.sm,
    paddingBottom: SPACING.md,
    backgroundColor: COLORS.surface,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(0,0,0,0.06)",
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    marginStart: 4,
  },
  title: {
    fontSize: 22,
    fontWeight: "900",
    color: COLORS.textPrimary,
    textAlign: "right",
    writingDirection: "rtl",
  },
  subtitle: {
    fontSize: 13,
    color: COLORS.textSecondary,
    marginTop: 4,
    textAlign: "right",
    writingDirection: "rtl",
    lineHeight: 18,
  },
  scroll: {
    padding: SPACING.md,
  },
  notice: {
    flexDirection: "row-reverse",
    alignItems: "flex-start",
    gap: 10,
    backgroundColor: "rgba(20,184,179,0.08)",
    borderWidth: 1,
    borderColor: "rgba(20,184,179,0.30)",
    borderRadius: RADIUS.md,
    padding: SPACING.md,
    marginBottom: SPACING.lg,
  },
  noticeText: {
    flex: 1,
    fontSize: 13,
    color: COLORS.textSecondary,
    lineHeight: 19,
    textAlign: "right",
    writingDirection: "rtl",
  },
  section: {
    marginBottom: SPACING.lg,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: "900",
    color: COLORS.textPrimary,
    textAlign: "right",
    writingDirection: "rtl",
    marginBottom: SPACING.sm,
    paddingHorizontal: 4,
  },
  row: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.md,
    padding: SPACING.sm + 2,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "rgba(0,0,0,0.06)",
  },
  rowGov: {
    backgroundColor: "rgba(20,184,179,0.08)",
    borderColor: "rgba(20,184,179,0.40)",
  },
  govEmoji: {
    fontSize: 18,
    marginEnd: 6,
  },
  rowLabel: {
    fontSize: 14,
    fontWeight: "700",
    color: COLORS.textPrimary,
    textAlign: "right",
    writingDirection: "rtl",
  },
  rowLabelGov: {
    color: COLORS.secondary,
  },
  rowUrl: {
    fontSize: 11,
    color: COLORS.textMuted,
    marginTop: 2,
    textAlign: "right",
    writingDirection: "rtl",
    ...Platform.select({ ios: { fontVariant: ["tabular-nums"] }, android: {} }),
  },
});
