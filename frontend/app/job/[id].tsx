'use client';

import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Image,
  TouchableOpacity,
  ActivityIndicator,
  Pressable,
  Modal,
  Dimensions,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import {
  api,
  openLink,
  openPhone,
  openEmail,
  openWhatsApp,
  formatJobPosted,
} from "../../api";
import { JobT } from "../../components";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { trackJobView, trackJobOutbound } from "../../utils/analytics";

const jobTypeLabel: Record<string, string> = {
  full_time: "משרה מלאה",
  part_time: "משרה חלקית",
  shifts: "משמרות",
  temporary: "זמני / עונתי",
  remote: "עבודה מהבית",
};

const expLabel: Record<string, string> = {
  none: "ללא דרישת ניסיון",
  required: "דרוש ניסיון",
};

const jobTagLabel: Record<string, { label: string; emoji: string }> = {
  hotels: { label: "מלונאות", emoji: "🏨" },
  restaurants: { label: "מסעדנות", emoji: "🍽️" },
  sales: { label: "מכירות", emoji: "💰" },
  retail: { label: "קמעונאות", emoji: "🛍️" },
  tourism: { label: "תיירות ופנאי", emoji: "🏖️" },
  call_center: { label: "מוקד ושירות לקוחות", emoji: "🎧" },
  security: { label: "אבטחה", emoji: "🛡️" },
  cleaning: { label: "ניקיון ואחזקה", emoji: "🧹" },
  logistics: { label: "הובלות ולוגיסטיקה", emoji: "🚚" },
  office: { label: "משרד ואדמיניסטרציה", emoji: "💼" },
  health: { label: "רפואה ובריאות", emoji: "🏥" },
  education: { label: "חינוך והדרכה", emoji: "📚" },
  construction: { label: "בנייה ותעשייה", emoji: "🚧" },
  tech: { label: "מחשבים והייטק", emoji: "💻" },
};

export default function JobDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<JobT | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imgOpen, setImgOpen] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const data = await api.job(String(id));
        if (alive) {
          setJob(data);
          if (data && data.id) {
            trackJobView(data.id, data.title);
          }
        }
      } catch (e: any) {
        if (alive) setError(e?.message || "שגיאה בטעינת המשרה");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [id]);

  if (loading) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <Header onBack={() => router.back()} title="משרה" />
        <View style={{ paddingVertical: 80, alignItems: "center" }}>
          <ActivityIndicator color={COLORS.primary} />
        </View>
      </SafeAreaView>
    );
  }

  if (error || !job) {
    return (
      <SafeAreaView style={styles.root} edges={["top"]}>
        <Header onBack={() => router.back()} title="משרה" />
        <View style={styles.errorWrap}>
          <Ionicons name="alert-circle-outline" size={48} color={COLORS.textMuted} />
          <Text style={styles.errorTitle}>לא נמצאה משרה</Text>
          {error ? <Text style={styles.errorSub}>{error}</Text> : null}
        </View>
      </SafeAreaView>
    );
  }

  const tags = (job.tags || [])
    .map((t) => jobTagLabel[t])
    .filter(Boolean);
  const applyMsg = `היי, אני מהאפליקציה אילתוש ומעוניין/ת במשרה: ${job.title}`;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <Header onBack={() => router.back()} title="פרטי המשרה" />

      <ScrollView contentContainerStyle={{ paddingBottom: 120 }}>
        {job.image ? (
          <View style={styles.heroWrap}>
            <Image source={{ uri: job.image }} style={styles.hero} resizeMode="cover" />
            <Pressable
              onPress={() => setImgOpen(true)}
              style={({ pressed }) => [styles.heroExpandBtn, pressed && { opacity: 0.8 }]}
              hitSlop={8}
            >
              <Ionicons name="expand-outline" size={18} color="#fff" />
              <Text style={styles.heroExpandText}>הצג מלא</Text>
            </Pressable>
          </View>
        ) : null}

        <View style={styles.body}>
          {/* Source / posted meta */}
          <View style={styles.topMetaRow}>
            {job.source_name ? (
              <View style={styles.sourcePill}>
                <Ionicons name="open-outline" size={11} color={COLORS.textMuted} />
                <Text style={styles.sourcePillText}>{job.source_name}</Text>
              </View>
            ) : null}
            <View style={{ flex: 1 }} />
            <Text style={styles.postedText}>{formatJobPosted(job.posted_at)}</Text>
          </View>

          <Text style={styles.title}>{job.title}</Text>
          {job.company ? <Text style={styles.company}>{job.company}</Text> : null}

          <View style={styles.locationRow}>
            <Ionicons name="location-outline" size={14} color={COLORS.textSecondary} />
            <Text style={styles.locationText}>{job.location || "אילת"}</Text>
          </View>

          {/* Tags (category chips) */}
          {tags.length > 0 ? (
            <View style={styles.tagsRow}>
              {tags.map((t, i) => (
                <View key={i} style={styles.tagPill}>
                  <Text style={styles.tagPillText}>{t.emoji} {t.label}</Text>
                </View>
              ))}
            </View>
          ) : null}

          {/* Attribute badges */}
          <View style={styles.attrRow}>
            {job.job_type && jobTypeLabel[job.job_type] ? (
              <AttrBadge icon="time-outline" label={jobTypeLabel[job.job_type]} />
            ) : null}
            {job.experience && expLabel[job.experience] ? (
              <AttrBadge
                icon="school-outline"
                label={expLabel[job.experience]}
                accent={job.experience === "none" ? "green" : undefined}
              />
            ) : null}
            {job.salary ? (
              <AttrBadge icon="cash-outline" label={job.salary} accent="green" />
            ) : null}
          </View>

          {/* Description */}
          <Text style={styles.sectionLabel}>תיאור המשרה</Text>
          <Text style={styles.description}>{job.description}</Text>

          {/* Also in X sources */}
          {job.also_in && job.also_in.length > 0 ? (
            <View style={styles.alsoInBlock}>
              <Ionicons name="copy-outline" size={14} color={COLORS.textSecondary} />
              <Text style={styles.alsoInText}>
                משרה זו מפורסמת גם ב: {job.also_in.join(" · ")}
              </Text>
            </View>
          ) : null}

          {/* Open source link */}
          {job.source_url ? (
            <Pressable
              onPress={() => {
                trackJobOutbound(job.id);
                openLink(job.source_url!);
              }}
              style={({ pressed }) => [styles.openSourceBtn, pressed && { opacity: 0.8 }]}
            >
              <Ionicons name="open-outline" size={16} color={COLORS.primary} />
              <Text style={styles.openSourceText}>פתח במודעה המקורית</Text>
            </Pressable>
          ) : null}
        </View>
      </ScrollView>

      {/* Bottom sticky apply bar */}
      {(job.phone || job.whatsapp || job.email) ? (
        <View style={styles.stickyBar}>
          {job.phone ? (
            <TouchableOpacity
              style={styles.callBtn}
              onPress={() => openPhone(job.phone as string)}
            >
              <Ionicons name="call" size={18} color="#fff" />
              <Text style={styles.callBtnText}>התקשר</Text>
            </TouchableOpacity>
          ) : null}
          {job.email ? (
            <TouchableOpacity
              style={styles.emailBtn}
              onPress={() => openEmail(
                job.email as string,
                `מעוניין/ת במשרה: ${job.title}`,
                `${applyMsg}\n\nלינק: ${job.source_url || ""}`,
              )}
            >
              <Ionicons name="mail" size={18} color="#fff" />
              <Text style={styles.emailBtnText}>מייל</Text>
            </TouchableOpacity>
          ) : null}
          {job.whatsapp ? (
            <TouchableOpacity
              style={styles.applyBtn}
              onPress={() => openWhatsApp(job.whatsapp as string, applyMsg)}
            >
              <Ionicons name="logo-whatsapp" size={18} color="#fff" />
              <Text style={styles.applyBtnText}>הגש מועמדות בוואטסאפ</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}

      {/* Fullscreen image viewer */}
      <Modal
        visible={imgOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setImgOpen(false)}
      >
        <Pressable style={styles.lightboxBackdrop} onPress={() => setImgOpen(false)}>
          <Pressable
            style={styles.lightboxClose}
            onPress={() => setImgOpen(false)}
            hitSlop={12}
          >
            <Ionicons name="close" size={26} color="#fff" />
          </Pressable>
          {job?.image ? (
            <Image
              source={{ uri: job.image }}
              style={styles.lightboxImg}
              resizeMode="contain"
            />
          ) : null}
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

function Header({ onBack, title }: { onBack: () => void; title: string }) {
  return (
    <View style={styles.header}>
      <Pressable onPress={onBack} style={styles.backBtn} hitSlop={10}>
        <Ionicons name="chevron-forward" size={24} color={COLORS.textPrimary} />
      </Pressable>
      <Text style={styles.headerTitle}>{title}</Text>
      <View style={{ width: 36 }} />
    </View>
  );
}

function AttrBadge({
  icon,
  label,
  accent,
}: {
  icon: any;
  label: string;
  accent?: "green" | "red";
}) {
  const bg =
    accent === "green"
      ? "rgba(20,184,179,0.10)"
      : accent === "red"
      ? "rgba(230,57,70,0.10)"
      : "rgba(15,23,42,0.05)";
  const color =
    accent === "green"
      ? COLORS.secondary
      : accent === "red"
      ? COLORS.primary
      : COLORS.textSecondary;
  const borderColor =
    accent === "green"
      ? "rgba(20,184,179,0.30)"
      : accent === "red"
      ? "rgba(230,57,70,0.30)"
      : "rgba(15,23,42,0.12)";
  return (
    <View style={[styles.attrBadge, { backgroundColor: bg, borderColor }]}>
      <Ionicons name={icon} size={13} color={color} />
      <Text style={[styles.attrBadgeText, { color }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingHorizontal: SPACING.sm,
    paddingVertical: SPACING.sm,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: COLORS.card,
  },
  backBtn: {
    width: 36,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 18,
  },
  headerTitle: {
    flex: 1,
    color: COLORS.textPrimary,
    fontSize: 16,
    fontWeight: "900",
    textAlign: "center",
  },
  hero: { width: "100%", height: 220 },
  heroWrap: { position: "relative" },
  heroExpandBtn: {
    position: "absolute",
    top: 10,
    end: 10,
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(15,23,42,0.72)",
  },
  heroExpandText: { color: "#fff", fontSize: 12, fontWeight: "800" },
  body: { paddingHorizontal: SPACING.md, paddingTop: SPACING.md },
  topMetaRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    marginBottom: SPACING.sm,
  },
  sourcePill: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(15,23,42,0.05)",
  },
  sourcePillText: { color: COLORS.textSecondary, fontSize: 11, fontWeight: "800" },
  postedText: { color: COLORS.textMuted, fontSize: 12 },
  title: {
    color: COLORS.textPrimary,
    fontSize: 24,
    fontWeight: "900",
    textAlign: "right",
    writingDirection: "rtl",
    lineHeight: 30,
  },
  company: {
    color: COLORS.secondary,
    fontSize: 15,
    fontWeight: "800",
    marginTop: 4,
    textAlign: "right",
  },
  locationRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    marginTop: 6,
  },
  locationText: { color: COLORS.textSecondary, fontSize: 13 },
  tagsRow: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 14,
  },
  tagPill: {
    backgroundColor: "rgba(230,57,70,0.10)",
    borderWidth: 1,
    borderColor: "rgba(230,57,70,0.30)",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: RADIUS.pill,
  },
  tagPillText: { color: COLORS.primary, fontSize: 12, fontWeight: "800" },
  attrRow: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 10,
  },
  attrBadge: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: RADIUS.pill,
    borderWidth: 1,
  },
  attrBadgeText: { fontSize: 12, fontWeight: "800" },
  sectionLabel: {
    color: COLORS.textPrimary,
    fontSize: 15,
    fontWeight: "900",
    marginTop: 22,
    marginBottom: 6,
    textAlign: "right",
  },
  description: {
    color: COLORS.textPrimary,
    fontSize: 15,
    lineHeight: 24,
    textAlign: "right",
    writingDirection: "rtl",
  },
  alsoInBlock: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 6,
    marginTop: 18,
    paddingVertical: 10,
    paddingHorizontal: 12,
    backgroundColor: "rgba(15,23,42,0.04)",
    borderRadius: RADIUS.md,
  },
  alsoInText: { color: COLORS.textSecondary, fontSize: 12, flex: 1, textAlign: "right" },
  openSourceBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    marginTop: 18,
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: RADIUS.md,
    backgroundColor: "rgba(230,57,70,0.08)",
    borderWidth: 1,
    borderColor: "rgba(230,57,70,0.30)",
  },
  openSourceText: { color: COLORS.primary, fontSize: 14, fontWeight: "800" },

  stickyBar: {
    position: "absolute",
    start: 0,
    end: 0,
    bottom: 0,
    flexDirection: "row-reverse",
    gap: 10,
    padding: SPACING.md,
    paddingBottom: SPACING.md + 6,
    backgroundColor: COLORS.card,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  callBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: RADIUS.pill,
    backgroundColor: COLORS.success,
  },
  callBtnText: { color: "#fff", fontWeight: "800", fontSize: 14 },
  emailBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 14,
    paddingHorizontal: 18,
    borderRadius: RADIUS.pill,
    backgroundColor: COLORS.accent,
  },
  emailBtnText: { color: "#fff", fontWeight: "800", fontSize: 14 },
  lightboxBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.95)",
    alignItems: "center",
    justifyContent: "center",
  },
  lightboxClose: {
    position: "absolute",
    top: 48,
    end: 20,
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 20,
    backgroundColor: "rgba(255,255,255,0.12)",
    zIndex: 10,
  },
  lightboxImg: {
    width: "100%",
    height: "90%",
  },
  applyBtn: {
    flex: 1,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingVertical: 14,
    paddingHorizontal: 16,
    borderRadius: RADIUS.pill,
    backgroundColor: COLORS.whatsapp,
  },
  applyBtnText: { color: "#fff", fontWeight: "900", fontSize: 14 },

  errorWrap: { paddingVertical: 80, alignItems: "center", gap: 8 },
  errorTitle: { color: COLORS.textPrimary, fontSize: 16, fontWeight: "800" },
  errorSub: { color: COLORS.textMuted, fontSize: 12 },
});
