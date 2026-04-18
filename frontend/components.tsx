import React from "react";
import { View, Text, StyleSheet, Image, TouchableOpacity, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS, RADIUS, SPACING } from "./theme";
import { openWhatsApp, openPhone, formatHebrewTime, formatJobPosted } from "./api";

export type EventT = {
  id: string;
  title: string;
  description: string;
  category: string;
  venue: string;
  image: string;
  starts_at: string;
  price?: string;
  whatsapp?: string;
  phone?: string;
  band?: "now" | "tonight" | "later";
};

export type BusinessT = {
  id: string;
  name: string;
  category: string;
  description: string;
  image: string;
  address: string;
  phone?: string;
  whatsapp?: string;
  open_hours: string;
  deal?: string;
  rating: number;
  tags: string[];
  open_now?: boolean;
};

export type JobT = {
  id: string;
  title: string;
  company: string;
  category: string;
  description: string;
  salary?: string;
  urgency: "now" | "soon" | "this_week";
  location: string;
  phone?: string;
  whatsapp?: string;
  posted_at: string;
};

export type NewsT = {
  id: string;
  title: string;
  summary: string;
  source: string;
  image?: string;
  published_at: string;
};

const categoryLabel: Record<string, string> = {
  party: "מסיבה",
  concert: "הופעה",
  show: "מופע",
  activity: "פעילות",
  food: "אוכל",
  sport: "ספורט",
  restaurant: "מסעדה",
  bar: "בר",
  cafe: "בית קפה",
  shop: "חנות",
  service: "שירות",
  beauty: "יופי",
  hotel: "מלון",
  tourism: "תיירות",
  retail: "קמעונאות",
};

const urgencyLabel: Record<string, string> = {
  now: "התחלה עכשיו",
  soon: "התחלה קרובה",
  this_week: "השבוע",
};

const sourceLabel: Record<string, string> = {
  municipality: "עירייה",
  alert: "התראה",
  event: "אירוע",
};

export function TimeBandBadge({ band }: { band?: string }) {
  if (!band) return null;
  const map: Record<string, { text: string; color: string; bg: string }> = {
    now: { text: "עכשיו", color: "#fff", bg: COLORS.primary },
    tonight: { text: "הערב", color: COLORS.secondary, bg: "rgba(0,242,254,0.15)" },
    later: { text: "בהמשך", color: COLORS.textSecondary, bg: "rgba(255,255,255,0.07)" },
  };
  const s = map[band] || map.later;
  return (
    <View style={[styles.bandBadge, { backgroundColor: s.bg }]}>
      {band === "now" && <View style={styles.pulseDot} />}
      <Text style={[styles.bandBadgeText, { color: s.color }]}>{s.text}</Text>
    </View>
  );
}

export function EventCard({ item }: { item: EventT }) {
  return (
    <View style={styles.eventCard} testID={`event-card-${item.id}`}>
      <Image source={{ uri: item.image }} style={styles.eventImage} />
      <View style={styles.eventImageOverlay} />
      <View style={styles.eventTopRow}>
        <TimeBandBadge band={item.band} />
        <Text style={styles.categoryPill}>{categoryLabel[item.category] || item.category}</Text>
      </View>
      <View style={styles.eventBody}>
        <Text style={styles.eventTitle} numberOfLines={2}>
          {item.title}
        </Text>
        <View style={styles.metaRow}>
          <Ionicons name="time-outline" size={14} color={COLORS.textSecondary} />
          <Text style={styles.metaText}>{formatHebrewTime(item.starts_at)}</Text>
          <Text style={styles.metaDot}>·</Text>
          <Ionicons name="location-outline" size={14} color={COLORS.textSecondary} />
          <Text style={styles.metaText} numberOfLines={1}>
            {item.venue}
          </Text>
        </View>
        <Text style={styles.eventDesc} numberOfLines={2}>
          {item.description}
        </Text>
        <View style={styles.actionsRow}>
          {item.price && (
            <View style={styles.pricePill}>
              <Text style={styles.pricePillText}>{item.price}</Text>
            </View>
          )}
          <View style={{ flex: 1 }} />
          {item.phone && (
            <TouchableOpacity
              style={styles.iconBtn}
              onPress={() => openPhone(item.phone)}
              testID={`event-call-${item.id}`}
            >
              <Ionicons name="call" size={16} color="#fff" />
            </TouchableOpacity>
          )}
          {item.whatsapp && (
            <TouchableOpacity
              style={[styles.iconBtn, { backgroundColor: COLORS.whatsapp }]}
              onPress={() => openWhatsApp(item.whatsapp, `היי, אני מהאפליקציה אילתוש ומתעניין ב־${item.title}`)}
              testID={`event-whatsapp-${item.id}`}
            >
              <Ionicons name="logo-whatsapp" size={16} color="#fff" />
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
  );
}

export function BusinessCard({ item }: { item: BusinessT }) {
  return (
    <View style={styles.bizCard} testID={`business-card-${item.id}`}>
      <Image source={{ uri: item.image }} style={styles.bizImage} />
      <View style={styles.bizBody}>
        <View style={styles.bizHeader}>
          <Text style={styles.bizName} numberOfLines={1}>
            {item.name}
          </Text>
          {item.open_now ? (
            <View style={styles.openDot}>
              <View style={styles.openDotInner} />
              <Text style={styles.openText}>פתוח</Text>
            </View>
          ) : (
            <View style={[styles.openDot, { backgroundColor: "rgba(239,68,68,0.12)" }]}>
              <Text style={[styles.openText, { color: COLORS.danger }]}>סגור</Text>
            </View>
          )}
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.categoryPillSmall}>{categoryLabel[item.category] || item.category}</Text>
          <Text style={styles.metaDot}>·</Text>
          <Ionicons name="star" size={12} color="#FFB020" />
          <Text style={styles.metaText}>{item.rating.toFixed(1)}</Text>
          <Text style={styles.metaDot}>·</Text>
          <Text style={styles.metaText}>{item.open_hours}</Text>
        </View>
        <Text style={styles.bizDesc} numberOfLines={2}>
          {item.description}
        </Text>
        {item.deal ? (
          <View style={styles.dealBadge}>
            <Ionicons name="pricetag" size={12} color={COLORS.primary} />
            <Text style={styles.dealText} numberOfLines={1}>
              {item.deal}
            </Text>
          </View>
        ) : null}
        <View style={styles.actionsRow}>
          <Text style={styles.addressText} numberOfLines={1}>
            {item.address}
          </Text>
          <View style={{ flex: 1 }} />
          {item.phone && (
            <TouchableOpacity
              style={styles.iconBtn}
              onPress={() => openPhone(item.phone)}
              testID={`business-call-${item.id}`}
            >
              <Ionicons name="call" size={16} color="#fff" />
            </TouchableOpacity>
          )}
          {item.whatsapp && (
            <TouchableOpacity
              style={[styles.iconBtn, { backgroundColor: COLORS.whatsapp }]}
              onPress={() => openWhatsApp(item.whatsapp, `היי, אני מהאפליקציה אילתוש ומתעניין ב־${item.name}`)}
              testID={`business-whatsapp-${item.id}`}
            >
              <Ionicons name="logo-whatsapp" size={16} color="#fff" />
            </TouchableOpacity>
          )}
        </View>
      </View>
    </View>
  );
}

export function JobCard({ item }: { item: JobT }) {
  const urg = item.urgency;
  const urgColor = urg === "now" ? COLORS.primary : urg === "soon" ? COLORS.secondary : COLORS.textSecondary;
  const urgBg = urg === "now" ? "rgba(230,57,70,0.10)" : urg === "soon" ? "rgba(20,184,179,0.10)" : "rgba(15,23,42,0.05)";
  return (
    <View style={styles.jobCard} testID={`job-card-${item.id}`}>
      <View style={styles.jobHeader}>
        <View style={[styles.urgencyPill, { backgroundColor: urgBg }]}>
          {urg === "now" && <View style={[styles.pulseDot, { backgroundColor: urgColor }]} />}
          <Text style={[styles.urgencyText, { color: urgColor }]}>{urgencyLabel[urg]}</Text>
        </View>
        <Text style={styles.categoryPillSmall}>{categoryLabel[item.category] || item.category}</Text>
        <View style={{ flex: 1 }} />
        <Text style={styles.jobPosted}>{formatJobPosted(item.posted_at)}</Text>
      </View>
      <Text style={styles.jobTitle} numberOfLines={2}>
        {item.title}
      </Text>
      <Text style={styles.jobCompany}>{item.company}</Text>
      <Text style={styles.jobDesc} numberOfLines={3}>
        {item.description}
      </Text>
      <View style={styles.jobFooter}>
        {item.salary && (
          <View style={styles.salaryPill}>
            <Ionicons name="cash-outline" size={14} color={COLORS.secondary} />
            <Text style={styles.salaryText}>{item.salary}</Text>
          </View>
        )}
        <View style={{ flex: 1 }} />
        {item.phone && (
          <TouchableOpacity
            style={styles.iconBtn}
            onPress={() => openPhone(item.phone)}
            testID={`job-call-${item.id}`}
          >
            <Ionicons name="call" size={16} color="#fff" />
          </TouchableOpacity>
        )}
        {item.whatsapp && (
          <TouchableOpacity
            style={[styles.applyBtn]}
            onPress={() => openWhatsApp(item.whatsapp, `היי, אני מהאפליקציה אילתוש ומעוניין/ת במשרה: ${item.title}`)}
            testID={`job-apply-${item.id}`}
          >
            <Ionicons name="logo-whatsapp" size={16} color="#fff" />
            <Text style={styles.applyBtnText}>הגש מועמדות</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

export function NewsCard({ item }: { item: NewsT }) {
  const color =
    item.source === "alert" ? COLORS.primary : item.source === "municipality" ? COLORS.secondary : COLORS.textSecondary;
  return (
    <View style={styles.newsCard} testID={`news-card-${item.id}`}>
      {item.image && <Image source={{ uri: item.image }} style={styles.newsImage} />}
      <View style={styles.newsBody}>
        <View style={styles.sourceRow}>
          <View style={[styles.sourceBadge, { borderColor: color }]}>
            <Text style={[styles.sourceText, { color }]}>{sourceLabel[item.source] || item.source}</Text>
          </View>
          <Text style={styles.newsDate}>{formatHebrewTime(item.published_at)}</Text>
        </View>
        <Text style={styles.newsTitle}>{item.title}</Text>
        <Text style={styles.newsSummary} numberOfLines={3}>
          {item.summary}
        </Text>
      </View>
    </View>
  );
}

export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <View style={{ marginTop: SPACING.lg, marginBottom: SPACING.sm, paddingHorizontal: SPACING.md }}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {subtitle ? <Text style={styles.sectionSub}>{subtitle}</Text> : null}
    </View>
  );
}

export function FilterChip({
  label,
  active,
  onPress,
  testID,
}: {
  label: string;
  active?: boolean;
  onPress: () => void;
  testID?: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      testID={testID}
      style={({ pressed }) => [
        styles.chip,
        active && styles.chipActive,
        pressed && { opacity: 0.7 },
      ]}
    >
      <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
    </Pressable>
  );
}

export function EmptyState({ icon = "search", title, subtitle }: { icon?: any; title: string; subtitle?: string }) {
  return (
    <View style={styles.empty}>
      <Ionicons name={icon} size={40} color={COLORS.textMuted} />
      <Text style={styles.emptyTitle}>{title}</Text>
      {subtitle ? <Text style={styles.emptySub}>{subtitle}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  eventCard: {
    backgroundColor: COLORS.card,
    borderRadius: RADIUS.lg,
    marginHorizontal: SPACING.md,
    marginBottom: SPACING.md,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: COLORS.border,
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  eventImage: { width: "100%", height: 140 },
  eventImageOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    height: 140,
    backgroundColor: "rgba(12,12,18,0.35)",
  },
  eventTopRow: {
    position: "absolute",
    top: 12,
    start: 12,
    end: 12,
    flexDirection: "row-reverse",
    justifyContent: "space-between",
    alignItems: "center",
  },
  eventBody: { padding: SPACING.md },
  eventTitle: {
    color: COLORS.textPrimary,
    fontSize: 18,
    fontWeight: "900",
    textAlign: "right",
    writingDirection: "rtl",
  },
  metaRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    marginTop: 6,
    flexWrap: "wrap",
  },
  metaText: { color: COLORS.textSecondary, fontSize: 12, marginHorizontal: 2, textAlign: "right" },
  metaDot: { color: COLORS.textMuted, marginHorizontal: 4 },
  eventDesc: {
    color: COLORS.textSecondary,
    fontSize: 13,
    marginTop: 8,
    textAlign: "right",
    writingDirection: "rtl",
    lineHeight: 18,
  },
  actionsRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    marginTop: 12,
    gap: 8,
  },
  pricePill: {
    backgroundColor: "rgba(15,23,42,0.06)",
    borderRadius: RADIUS.pill,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  pricePillText: { color: COLORS.textPrimary, fontSize: 12, fontWeight: "700" },
  iconBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: COLORS.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  bandBadge: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: RADIUS.pill,
    gap: 6,
  },
  bandBadgeText: { fontSize: 11, fontWeight: "900", letterSpacing: 0.5 },
  pulseDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: "#fff",
    marginEnd: 2,
  },
  categoryPill: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "700",
    paddingHorizontal: 8,
    paddingVertical: 3,
    backgroundColor: "rgba(15,23,42,0.65)",
    borderRadius: RADIUS.pill,
    overflow: "hidden",
  },
  categoryPillSmall: {
    color: COLORS.textSecondary,
    fontSize: 11,
    fontWeight: "700",
    paddingHorizontal: 8,
    paddingVertical: 2,
    backgroundColor: "rgba(15,23,42,0.05)",
    borderRadius: RADIUS.pill,
    overflow: "hidden",
  },

  // Biz
  bizCard: {
    flexDirection: "row-reverse",
    backgroundColor: COLORS.card,
    borderRadius: RADIUS.lg,
    marginHorizontal: SPACING.md,
    marginBottom: SPACING.md,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: COLORS.border,
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  bizImage: { width: 110, height: "100%", minHeight: 140 },
  bizBody: { flex: 1, padding: 12 },
  bizHeader: { flexDirection: "row-reverse", alignItems: "center", justifyContent: "space-between" },
  bizName: { color: COLORS.textPrimary, fontSize: 16, fontWeight: "900", flex: 1, textAlign: "right" },
  openDot: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: "rgba(34,197,94,0.14)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: RADIUS.pill,
    gap: 4,
  },
  openDotInner: { width: 6, height: 6, borderRadius: 3, backgroundColor: COLORS.success },
  openText: { color: COLORS.success, fontSize: 11, fontWeight: "800" },
  bizDesc: { color: COLORS.textSecondary, fontSize: 12, marginTop: 6, textAlign: "right", writingDirection: "rtl" },
  dealBadge: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: "rgba(230,57,70,0.08)",
    borderColor: "rgba(230,57,70,0.35)",
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: RADIUS.md,
    marginTop: 8,
    gap: 6,
    alignSelf: "flex-end",
  },
  dealText: { color: COLORS.primary, fontSize: 12, fontWeight: "800" },
  addressText: { color: COLORS.textMuted, fontSize: 11, textAlign: "right", flexShrink: 1 },

  // Job
  jobCard: {
    backgroundColor: COLORS.card,
    borderRadius: RADIUS.lg,
    padding: SPACING.md,
    marginHorizontal: SPACING.md,
    marginBottom: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  jobHeader: { flexDirection: "row-reverse", alignItems: "center", gap: 6, flexWrap: "wrap" },
  urgencyPill: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: RADIUS.pill,
    gap: 6,
  },
  urgencyText: { fontSize: 11, fontWeight: "900", letterSpacing: 0.3 },
  jobPosted: { color: COLORS.textMuted, fontSize: 11 },
  jobTitle: { color: COLORS.textPrimary, fontSize: 17, fontWeight: "900", marginTop: 10, textAlign: "right", writingDirection: "rtl" },
  jobCompany: { color: COLORS.secondary, fontSize: 13, fontWeight: "700", marginTop: 2, textAlign: "right" },
  jobDesc: { color: COLORS.textSecondary, fontSize: 13, marginTop: 8, textAlign: "right", writingDirection: "rtl", lineHeight: 19 },
  jobFooter: { flexDirection: "row-reverse", alignItems: "center", marginTop: 12, gap: 8 },
  salaryPill: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: "rgba(20,184,179,0.08)",
    borderColor: "rgba(20,184,179,0.30)",
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: RADIUS.pill,
    gap: 4,
  },
  salaryText: { color: COLORS.secondary, fontSize: 12, fontWeight: "800" },
  applyBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: COLORS.whatsapp,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: RADIUS.pill,
    gap: 6,
  },
  applyBtnText: { color: "#fff", fontWeight: "800", fontSize: 13 },

  // News
  newsCard: {
    backgroundColor: COLORS.card,
    borderRadius: RADIUS.lg,
    marginHorizontal: SPACING.md,
    marginBottom: SPACING.md,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: COLORS.border,
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  newsImage: { width: "100%", height: 140 },
  newsBody: { padding: SPACING.md },
  sourceRow: { flexDirection: "row-reverse", justifyContent: "space-between", alignItems: "center", marginBottom: 8 },
  sourceBadge: { borderWidth: 1, paddingHorizontal: 8, paddingVertical: 2, borderRadius: RADIUS.sm },
  sourceText: { fontSize: 11, fontWeight: "900", letterSpacing: 0.4 },
  newsDate: { color: COLORS.textMuted, fontSize: 11 },
  newsTitle: { color: COLORS.textPrimary, fontSize: 16, fontWeight: "900", textAlign: "right", writingDirection: "rtl" },
  newsSummary: { color: COLORS.textSecondary, fontSize: 13, marginTop: 6, lineHeight: 20, textAlign: "right", writingDirection: "rtl" },

  // Section
  sectionTitle: { color: COLORS.textPrimary, fontSize: 22, fontWeight: "900", textAlign: "right", writingDirection: "rtl" },
  sectionSub: { color: COLORS.textMuted, fontSize: 13, marginTop: 2, textAlign: "right" },

  // Chip
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: RADIUS.pill,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: COLORS.border,
    marginEnd: 8,
  },
  chipActive: {
    backgroundColor: "rgba(230,57,70,0.10)",
    borderColor: "rgba(230,57,70,0.45)",
  },
  chipText: { color: COLORS.textSecondary, fontSize: 13, fontWeight: "700" },
  chipTextActive: { color: COLORS.primary },

  // Empty
  empty: { alignItems: "center", justifyContent: "center", paddingVertical: 60 },
  emptyTitle: { color: COLORS.textPrimary, fontSize: 16, fontWeight: "800", marginTop: 12 },
  emptySub: { color: COLORS.textMuted, fontSize: 13, marginTop: 6, textAlign: "center" },
});
