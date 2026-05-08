import React from "react";
import { View, Text, StyleSheet, Image, TouchableOpacity, Pressable, Linking } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS, RADIUS, SPACING } from "./theme";
import { openWhatsApp, openPhone, openLink, formatHebrewTime, formatJobPosted } from "./api";

export type EventT = {
  id: string;
  title: string;
  description?: string | null;
  category?: string | null;
  venue?: string | null;
  image?: string | null;
  starts_at: string;
  price?: string;
  whatsapp?: string;
  phone?: string;
  link?: string | null;
  source?: string | null;
  tags?: string[];
  band?: "now" | "tonight" | "later";
};

/** Visual mapping for event categories / tags when no photo is available. */
const EVENT_VISUAL: Record<
  string,
  { icon: keyof typeof Ionicons.glyphMap; color: string; bg: string }
> = {
  cinema:     { icon: "film",          color: "#7C3AED", bg: "#EDE9FE" },
  concert:    { icon: "musical-notes", color: "#DB2777", bg: "#FCE7F3" },
  party:      { icon: "wine",          color: "#F97316", bg: "#FFEDD5" },
  show:       { icon: "mic",           color: "#0EA5E9", bg: "#E0F2FE" },
  sport:      { icon: "basketball",    color: "#16A34A", bg: "#DCFCE7" },
  food:       { icon: "restaurant",    color: "#EA580C", bg: "#FFEDD5" },
  activity:   { icon: "sparkles",      color: "#14B8B3", bg: "#CCFBF1" },
  kids:       { icon: "balloon",       color: "#F472B6", bg: "#FCE7F3" },
  default:    { icon: "calendar",      color: "#14B8B3", bg: "#CCFBF1" },
};
function eventVisual(item: EventT) {
  const key = (item.tags?.[0] || item.category || "default").toLowerCase();
  return EVENT_VISUAL[key] || EVENT_VISUAL.default;
}

export type BusinessT = {
  id: string;
  type: "business" | "professional";
  name: string;
  subtitle?: string | null;
  description?: string;
  address?: string | null;
  phone?: string | null;
  whatsapp?: string | null;
  email?: string | null;
  website?: string | null;
  open_hours?: string | null;
  image?: string | null;
  source?: string;
  source_name?: string;
  source_url?: string;
  category_hint?: string | null;
  tags?: string[];
  also_in?: string[];
  open_now?: boolean;
};

export type JobT = {
  id: string;
  title: string;
  company?: string | null;
  category?: string;
  description: string;
  salary?: string | null;
  urgency?: "now" | "soon" | "this_week";
  location: string;
  phone?: string | null;
  whatsapp?: string | null;
  posted_at: string;
  // New fields from scrapers:
  source?: string;
  source_name?: string;
  source_url?: string;
  job_type?: "full_time" | "part_time" | "shifts" | "temporary" | "remote" | null;
  experience?: "none" | "required" | null;
  tags?: string[];
  image?: string | null;
  also_in?: string[];
};

export type NewsT = {
  id: string;
  title: string;
  summary: string;
  source: string;
  source_name?: string;
  source_url?: string;
  source_type?: "news" | "alert" | "event";
  content_html?: string;
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
  const vis = eventVisual(item);
  const [imageFailed, setImageFailed] = React.useState(false);
  const hasImage = !!item.image && !imageFailed;
  const hasVenue = !!(item.venue && String(item.venue).trim().length);
  const hasDesc = !!(item.description && String(item.description).trim().length);
  const canOpen = !!item.link;
  const handleOpen = () => {
    if (item.link) openLink(item.link);
  };
  return (
    <Pressable
      onPress={handleOpen}
      disabled={!canOpen}
      style={({ pressed }) => [
        styles.eventCard,
        pressed && canOpen && { opacity: 0.85, transform: [{ scale: 0.995 }] },
      ]}
      testID={`event-card-${item.id}`}
    >
      {hasImage ? (
        <>
          <Image
            source={{ uri: item.image! }}
            style={styles.eventImage}
            onError={() => setImageFailed(true)}
          />
          <View style={styles.eventImageOverlay} />
        </>
      ) : (
        <View style={[styles.eventImage, styles.eventImagePlaceholder, { backgroundColor: vis.bg }]}>
          <Ionicons name={vis.icon} size={72} color={vis.color} />
        </View>
      )}
      <View style={styles.eventTopRow}>
        <TimeBandBadge band={item.band} />
        {item.category ? (
          <Text style={styles.categoryPill}>{categoryLabel[item.category] || item.category}</Text>
        ) : null}
      </View>
      <View style={styles.eventBody}>
        <Text style={styles.eventTitle} numberOfLines={2}>
          {item.title}
        </Text>
        <View style={styles.metaRow}>
          <Ionicons name="time-outline" size={14} color={COLORS.textSecondary} />
          <Text style={styles.metaText}>{formatHebrewTime(item.starts_at)}</Text>
          {hasVenue ? (
            <>
              <Text style={styles.metaDot}>·</Text>
              <Ionicons name="location-outline" size={14} color={COLORS.textSecondary} />
              <Text style={styles.metaText} numberOfLines={1}>
                {item.venue}
              </Text>
            </>
          ) : null}
        </View>
        {hasDesc ? (
          <Text style={styles.eventDesc} numberOfLines={2}>
            {item.description}
          </Text>
        ) : null}
        <View style={styles.actionsRow}>
          {item.price && (
            <View style={styles.pricePill}>
              <Text style={styles.pricePillText}>{item.price}</Text>
            </View>
          )}
          <View style={{ flex: 1 }} />
          {canOpen ? (
            <View style={styles.linkPill}>
              <Ionicons name="open-outline" size={13} color={COLORS.primary} />
              <Text style={styles.linkPillText}>לפרטים</Text>
            </View>
          ) : null}
          {item.phone && (
            <TouchableOpacity
              style={styles.iconBtn}
              onPress={(e: any) => {
                e.stopPropagation?.();
                openPhone(item.phone);
              }}
              testID={`event-call-${item.id}`}
            >
              <Ionicons name="call" size={16} color="#fff" />
            </TouchableOpacity>
          )}
          {item.whatsapp && (
            <TouchableOpacity
              style={[styles.iconBtn, { backgroundColor: COLORS.whatsapp }]}
              onPress={(e: any) => {
                e.stopPropagation?.();
                openWhatsApp(item.whatsapp, `היי, אני מהאפליקציה אילתוש ומתעניין ב־${item.title}`);
              }}
              testID={`event-whatsapp-${item.id}`}
            >
              <Ionicons name="logo-whatsapp" size={16} color="#fff" />
            </TouchableOpacity>
          )}
        </View>
      </View>
    </Pressable>
  );
}

export const BIZ_CATEGORY: Record<string, { label: string; emoji: string; icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  restaurants:     { label: "מסעדות",          emoji: "🍽️", icon: "restaurant",              color: "#F97316" },
  cafes:           { label: "בתי קפה",         emoji: "☕", icon: "cafe",                    color: "#8B4513" },
  bars:            { label: "פאבים וברים",      emoji: "🍺", icon: "beer",                    color: "#D97706" },
  fast_food:       { label: "מזון מהיר",        emoji: "🍔", icon: "fast-food",               color: "#EA580C" },
  attractions:     { label: "אטרקציות",        emoji: "🎢", icon: "happy",                   color: "#DB2777" },
  hotels:          { label: "מלונאות",         emoji: "🏨", icon: "bed",                     color: "#7C3AED" },
  spa:             { label: "ספא",             emoji: "💆", icon: "sparkles",                color: "#EC4899" },
  beauty:          { label: "יופי",            emoji: "💅", icon: "rose",                    color: "#EC4899" },
  fashion:         { label: "אופנה",           emoji: "👗", icon: "shirt",                   color: "#8B5CF6" },
  jewelry:         { label: "תכשיטים",         emoji: "💍", icon: "diamond",                 color: "#0EA5E9" },
  electronics:     { label: "אלקטרוניקה",      emoji: "💻", icon: "laptop",                  color: "#3B82F6" },
  appliances:      { label: "חשמל ביתי",       emoji: "🔌", icon: "bulb",                    color: "#F59E0B" },
  phones:          { label: "סלולר",           emoji: "📱", icon: "phone-portrait",          color: "#10B981" },
  home:            { label: "ריהוט",           emoji: "🛋️", icon: "home",                    color: "#92400E" },
  supermarket:     { label: "סופר",            emoji: "🛒", icon: "cart",                    color: "#16A34A" },
  shopping_center: { label: "מרכזי קניות",     emoji: "🏬", icon: "bag-handle",              color: "#A855F7" },
  travel:          { label: "משרדי נסיעות",    emoji: "✈️", icon: "airplane",                color: "#0284C7" },
  transport:       { label: "תחבורה",          emoji: "🚗", icon: "car",                     color: "#1E40AF" },
  marine:          { label: "ספורט ימי",       emoji: "🤿", icon: "boat",                    color: "#0891B2" },
  consulate:       { label: "קונסוליות",       emoji: "🏛️", icon: "business",                color: "#6B7280" },
  services_biz:    { label: "שירותים",         emoji: "🧾", icon: "briefcase",               color: "#64748B" },
  // Professionals
  construction:    { label: "שיפוצים",         emoji: "🏗️", icon: "hammer",                  color: "#F59E0B" },
  electrician:     { label: "חשמלאות",         emoji: "⚡", icon: "flash",                   color: "#EAB308" },
  plumber:         { label: "אינסטלציה",       emoji: "🔧", icon: "water",                   color: "#0EA5E9" },
  ac:              { label: "מיזוג",           emoji: "❄️", icon: "snow",                    color: "#38BDF8" },
  appliance_fix:   { label: "תיקון חשמל",      emoji: "🔌", icon: "hardware-chip",           color: "#F59E0B" },
  carpentry:       { label: "נגרות",           emoji: "🪚", icon: "build",                   color: "#92400E" },
  sealing:         { label: "איטום",           emoji: "🧱", icon: "layers",                  color: "#B45309" },
  cleaning_pro:    { label: "ניקיון",          emoji: "🧹", icon: "sparkles",                color: "#22D3EE" },
  gardening:       { label: "גינון",           emoji: "🌳", icon: "leaf",                    color: "#16A34A" },
  moving:          { label: "הובלות",          emoji: "📦", icon: "cube",                    color: "#CA8A04" },
  locksmith:       { label: "מנעולנות",        emoji: "🔑", icon: "key",                     color: "#D97706" },
  pest:            { label: "הדברה",           emoji: "🐛", icon: "bug",                     color: "#65A30D" },
  auto_repair:     { label: "מוסכים",          emoji: "🚙", icon: "car-sport",               color: "#1E40AF" },
  tutor:           { label: "מורים פרטיים",    emoji: "📚", icon: "school",                  color: "#9333EA" },
  therapy:         { label: "טיפול רגשי",      emoji: "💭", icon: "heart",                   color: "#E11D48" },
  health_pro:      { label: "בריאות",          emoji: "🏥", icon: "medical",                 color: "#DC2626" },
  lawyer:          { label: "עו״ד",            emoji: "⚖️", icon: "library",                 color: "#1F2937" },
  accountant:      { label: "רו״ח",            emoji: "🧮", icon: "calculator",              color: "#0F766E" },
  tech_pro:        { label: "מחשבים",          emoji: "💻", icon: "desktop",                 color: "#2563EB" },
  graphics:        { label: "גרפיקה",          emoji: "🎨", icon: "color-palette",           color: "#DB2777" },
  photo:           { label: "צילום",           emoji: "📷", icon: "camera",                  color: "#7C3AED" },
  events_pro:      { label: "אירועים",         emoji: "🎉", icon: "balloon",                 color: "#F472B6" },
  beauty_home:     { label: "יופי ביתי",        emoji: "💇", icon: "cut",                     color: "#EC4899" },
  realestate:      { label: "נדל״ן ותיווך",      emoji: "🏠", icon: "home",                   color: "#0EA5E9" },
};

export function BusinessCard({ item, onPress }: { item: BusinessT; onPress?: () => void }) {
  const isPro = item.type === "professional";
  const primaryTag = (item.tags || [])[0];
  const tagInfo = primaryTag ? BIZ_CATEGORY[primaryTag] : null;
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.bizCard, pressed && { opacity: 0.85 }]}
      testID={`business-card-${item.id}`}
    >
      {!isPro && item.image ? (
        <Image source={{ uri: item.image }} style={styles.bizImage} />
      ) : (
        <View
          style={[
            styles.bizImage,
            styles.bizImagePlaceholder,
            isPro && tagInfo ? { backgroundColor: tagInfo.color + "18" } : null,
          ]}
        >
          <Ionicons
            name={
              isPro
                ? (tagInfo?.icon || "construct-outline")
                : (tagInfo?.icon || "storefront-outline")
            }
            size={34}
            color={isPro && tagInfo ? tagInfo.color : COLORS.textMuted}
          />
        </View>
      )}
      <View style={styles.bizBody}>
        <View style={styles.bizHeader}>
          <Text style={styles.bizName} numberOfLines={1}>
            {item.name}
          </Text>
          {!isPro && item.open_hours ? (
            item.open_now ? (
              <View style={styles.openDot}>
                <View style={styles.openDotInner} />
                <Text style={styles.openText}>פתוח</Text>
              </View>
            ) : (
              <View style={[styles.openDot, { backgroundColor: "rgba(239,68,68,0.12)" }]}>
                <Text style={[styles.openText, { color: COLORS.danger }]}>סגור</Text>
              </View>
            )
          ) : null}
        </View>
        {item.subtitle ? (
          <Text style={styles.bizSubtitle} numberOfLines={1}>
            {item.subtitle}
          </Text>
        ) : null}
        <View style={styles.metaRow}>
          {tagInfo ? (
            <Text style={styles.categoryPillSmall}>
              {tagInfo.emoji} {tagInfo.label}
            </Text>
          ) : null}
          {item.open_hours ? (
            <>
              {tagInfo ? <Text style={styles.metaDot}>·</Text> : null}
              <Ionicons name="time-outline" size={11} color={COLORS.textMuted} />
              <Text style={styles.metaText} numberOfLines={1}>
                {item.open_hours}
              </Text>
            </>
          ) : null}
        </View>
        {item.address ? (
          <View style={styles.addrRow}>
            <Ionicons name="location-outline" size={12} color={COLORS.textMuted} />
            <Text style={styles.addressText} numberOfLines={1}>
              {item.address}
            </Text>
          </View>
        ) : null}
        <View style={styles.actionsRow}>
          <View style={{ flex: 1 }} />
          {item.phone ? (
            <TouchableOpacity
              style={[styles.iconBtn, { backgroundColor: COLORS.success }]}
              onPress={(e) => { e.stopPropagation(); openPhone(item.phone || undefined); }}
              testID={`business-call-${item.id}`}
            >
              <Ionicons name="call" size={16} color="#fff" />
            </TouchableOpacity>
          ) : null}
          {item.whatsapp ? (
            <TouchableOpacity
              style={[styles.iconBtn, { backgroundColor: COLORS.whatsapp }]}
              onPress={(e) => {
                e.stopPropagation();
                openWhatsApp(
                  item.whatsapp || undefined,
                  `היי, ראיתי אותך באפליקציית אילתוש ואשמח לקבל פרטים על ${item.name}`,
                );
              }}
              testID={`business-whatsapp-${item.id}`}
            >
              <Ionicons name="logo-whatsapp" size={16} color="#fff" />
            </TouchableOpacity>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

const jobTypeLabel: Record<string, string> = {
  full_time: "משרה מלאה",
  part_time: "משרה חלקית",
  shifts: "משמרות",
  temporary: "זמני",
  remote: "מהבית",
};

const expLabel: Record<string, string> = {
  none: "ללא ניסיון",
  required: "דרוש ניסיון",
};

const jobTagLabel: Record<string, { label: string; emoji: string }> = {
  hotels: { label: "מלונאות", emoji: "🏨" },
  restaurants: { label: "מסעדנות", emoji: "🍽️" },
  sales: { label: "מכירות", emoji: "💰" },
  retail: { label: "קמעונאות", emoji: "🛍️" },
  tourism: { label: "תיירות", emoji: "🏖️" },
  call_center: { label: "מוקד", emoji: "🎧" },
  security: { label: "אבטחה", emoji: "🛡️" },
  cleaning: { label: "ניקיון", emoji: "🧹" },
  logistics: { label: "לוגיסטיקה", emoji: "🚚" },
  office: { label: "משרד", emoji: "💼" },
  health: { label: "בריאות", emoji: "🏥" },
  education: { label: "חינוך", emoji: "📚" },
  construction: { label: "בנייה", emoji: "🚧" },
  tech: { label: "הייטק", emoji: "💻" },
};

export function JobCard({ item, onPress }: { item: JobT; onPress?: () => void }) {
  const hasImage = !!item.image;
  const primaryTag = (item.tags || [])[0];
  const tagInfo = primaryTag ? jobTagLabel[primaryTag] : null;
  const applyMsg = `היי, אני מהאפליקציה אילתוש ומעוניין/ת במשרה: ${item.title}`;
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.jobCard, pressed && { opacity: 0.85 }]} testID={`job-card-${item.id}`}>
      {hasImage ? (
        <View style={styles.jobImageWrap}>
          <Image source={{ uri: item.image as string }} style={styles.jobImage} />
          <View style={styles.jobImageHint} pointerEvents="none">
            <Ionicons name="expand-outline" size={14} color="#fff" />
          </View>
        </View>
      ) : null}
      <View style={styles.jobBody}>
        <View style={styles.jobHeader}>
          {tagInfo ? (
            <View style={styles.jobTagPill}>
              <Text style={styles.jobTagPillText}>{tagInfo.emoji} {tagInfo.label}</Text>
            </View>
          ) : null}
          {item.source_name ? (
            <View style={styles.jobSourcePill}>
              <Ionicons name="open-outline" size={10} color={COLORS.textMuted} style={{ marginEnd: 3 }} />
              <Text style={styles.jobSourceText} numberOfLines={1}>{item.source_name}</Text>
            </View>
          ) : null}
          <View style={{ flex: 1 }} />
          <Text style={styles.jobPosted}>{formatJobPosted(item.posted_at)}</Text>
        </View>
        <Text style={styles.jobTitle} numberOfLines={2}>{item.title}</Text>
        {item.company ? <Text style={styles.jobCompany}>{item.company}</Text> : null}
        <Text style={styles.jobDesc} numberOfLines={3}>{item.description}</Text>

        {/* Attribute badges row */}
        {(item.job_type || item.experience || item.salary) ? (
          <View style={styles.attrRow}>
            {item.job_type && jobTypeLabel[item.job_type] ? (
              <View style={styles.attrPill}>
                <Ionicons name="time-outline" size={12} color={COLORS.textSecondary} />
                <Text style={styles.attrText}>{jobTypeLabel[item.job_type]}</Text>
              </View>
            ) : null}
            {item.experience && expLabel[item.experience] ? (
              <View style={[styles.attrPill, item.experience === "none" && { backgroundColor: "rgba(20,184,179,0.10)", borderColor: "rgba(20,184,179,0.30)" }]}>
                <Ionicons name="school-outline" size={12} color={item.experience === "none" ? COLORS.secondary : COLORS.textSecondary} />
                <Text style={[styles.attrText, item.experience === "none" && { color: COLORS.secondary }]}>{expLabel[item.experience]}</Text>
              </View>
            ) : null}
            {item.salary ? (
              <View style={styles.salaryPill}>
                <Ionicons name="cash-outline" size={12} color={COLORS.secondary} />
                <Text style={styles.salaryText}>{item.salary}</Text>
              </View>
            ) : null}
          </View>
        ) : null}

        {item.also_in && item.also_in.length > 0 ? (
          <Text style={styles.alsoInText} numberOfLines={1}>
            גם ב־{item.also_in.slice(0, 2).join(" · ")}
          </Text>
        ) : null}

        <View style={styles.jobFooter}>
          {item.source_url ? (
            <Pressable
              onPress={(e: any) => { e?.stopPropagation?.(); item.source_url && require("./api").openLink(item.source_url); }}
              style={styles.openSourceBtn}
            >
              <Ionicons name="open-outline" size={14} color={COLORS.primary} />
              <Text style={styles.openSourceText}>פתח במקור</Text>
            </Pressable>
          ) : null}
          <View style={{ flex: 1 }} />
          {item.phone ? (
            <TouchableOpacity
              style={[styles.iconBtn, { backgroundColor: COLORS.success }]}
              onPress={(e: any) => { e?.stopPropagation?.(); openPhone(item.phone as string); }}
              testID={`job-call-${item.id}`}
            >
              <Ionicons name="call" size={16} color="#fff" />
            </TouchableOpacity>
          ) : null}
          {item.email ? (
            <TouchableOpacity
              style={[styles.iconBtn, { backgroundColor: COLORS.accent }]}
              onPress={(e: any) => {
                e?.stopPropagation?.();
                require("./api").openEmail(
                  item.email as string,
                  `מעוניין/ת במשרה: ${item.title}`,
                  applyMsg,
                );
              }}
              testID={`job-email-${item.id}`}
            >
              <Ionicons name="mail" size={16} color="#fff" />
            </TouchableOpacity>
          ) : null}
          {item.whatsapp ? (
            <TouchableOpacity
              style={styles.applyBtn}
              onPress={(e: any) => { e?.stopPropagation?.(); openWhatsApp(item.whatsapp as string, applyMsg); }}
              testID={`job-apply-${item.id}`}
            >
              <Ionicons name="logo-whatsapp" size={16} color="#fff" />
              <Text style={styles.applyBtnText}>הגש מועמדות</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

export function NewsCard({ item, onPress, onSourcePress }: { item: NewsT; onPress?: () => void; onSourcePress?: () => void }) {
  const stype = item.source_type || item.source || "news";
  const color =
    stype === "alert" ? COLORS.primary : stype === "event" ? COLORS.secondary : COLORS.accent;
  const srcLabel = item.source_name || sourceLabel[stype] || stype;
  return (
    <TouchableOpacity activeOpacity={0.85} onPress={onPress} style={styles.newsCard} testID={`news-card-${item.id}`}>
      {item.image ? <Image source={{ uri: item.image }} style={styles.newsImage} /> : null}
      <View style={styles.newsBody}>
        <View style={styles.sourceRow}>
          <Pressable
            onPress={(e: any) => {
              e?.stopPropagation?.();
              onSourcePress?.();
            }}
            style={[styles.sourceBadge, { borderColor: color }]}
            testID={`news-source-${item.id}`}
          >
            <Ionicons name="open-outline" size={10} color={color} style={{ marginEnd: 4 }} />
            <Text style={[styles.sourceText, { color }]} numberOfLines={1}>
              {srcLabel}
            </Text>
          </Pressable>
          <Text style={styles.newsDate}>{item.published_at ? formatHebrewTime(item.published_at) : ""}</Text>
        </View>
        <Text style={styles.newsTitle}>{item.title}</Text>
        <Text style={styles.newsSummary} numberOfLines={3}>
          {item.summary}
        </Text>
        <View style={styles.readMoreRow}>
          <Ionicons name="chevron-back" size={16} color={COLORS.primary} />
          <Text style={styles.readMoreText}>קרא עוד</Text>
        </View>
      </View>
    </TouchableOpacity>
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
  eventImagePlaceholder: {
    alignItems: "center",
    justifyContent: "center",
  },
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
  linkPill: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(20,184,179,0.12)",
    borderWidth: 1,
    borderColor: "rgba(20,184,179,0.35)",
  },
  linkPillText: { color: COLORS.primary, fontSize: 12, fontWeight: "800" },
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
  bizImagePlaceholder: {
    backgroundColor: "#F1F5F9",
    alignItems: "center",
    justifyContent: "center",
  },
  bizSubtitle: {
    color: COLORS.textSecondary,
    fontSize: 13,
    fontWeight: "600",
    marginTop: 2,
    textAlign: "right",
    writingDirection: "rtl",
  },
  addrRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    marginTop: 6,
  },
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
    marginHorizontal: SPACING.md,
    marginBottom: SPACING.md,
    borderWidth: 1,
    borderColor: COLORS.border,
    overflow: "hidden",
    shadowColor: "#0F172A",
    shadowOpacity: 0.05,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  jobImage: { width: "100%", height: 130 },
  jobImageWrap: { position: "relative" },
  jobImageHint: {
    position: "absolute",
    top: 8,
    end: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "rgba(15,23,42,0.65)",
    alignItems: "center",
    justifyContent: "center",
  },
  jobBody: { padding: SPACING.md },
  jobHeader: { flexDirection: "row-reverse", alignItems: "center", gap: 6, flexWrap: "wrap" },
  jobTagPill: {
    backgroundColor: "rgba(230,57,70,0.10)",
    borderRadius: RADIUS.pill,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderWidth: 1,
    borderColor: "rgba(230,57,70,0.30)",
  },
  jobTagPillText: { color: COLORS.primary, fontSize: 11, fontWeight: "800" },
  jobSourcePill: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: "rgba(15,23,42,0.05)",
    borderRadius: RADIUS.sm,
    paddingHorizontal: 6,
    paddingVertical: 3,
    maxWidth: 140,
  },
  jobSourceText: { color: COLORS.textMuted, fontSize: 10, fontWeight: "700" },
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
  attrRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 6,
    marginTop: 10,
  },
  attrPill: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: "rgba(15,23,42,0.05)",
    borderColor: "rgba(15,23,42,0.12)",
    borderWidth: 1,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: RADIUS.pill,
    gap: 4,
  },
  attrText: { color: COLORS.textSecondary, fontSize: 11, fontWeight: "700" },
  alsoInText: { color: COLORS.textMuted, fontSize: 11, marginTop: 6, textAlign: "right", fontStyle: "italic" },
  openSourceBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 8,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(230,57,70,0.07)",
    borderWidth: 1,
    borderColor: "rgba(230,57,70,0.25)",
  },
  openSourceText: { color: COLORS.primary, fontSize: 12, fontWeight: "800" },
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
  sourceBadge: {
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: RADIUS.sm,
    flexDirection: "row-reverse",
    alignItems: "center",
    maxWidth: "70%",
  },
  sourceText: { fontSize: 11, fontWeight: "900", letterSpacing: 0.4 },
  newsDate: { color: COLORS.textMuted, fontSize: 11 },
  newsTitle: { color: COLORS.textPrimary, fontSize: 16, fontWeight: "900", textAlign: "right", writingDirection: "rtl" },
  newsSummary: { color: COLORS.textSecondary, fontSize: 13, marginTop: 6, lineHeight: 20, textAlign: "right", writingDirection: "rtl" },
  readMoreRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "flex-end",
    marginTop: 10,
    gap: 4,
  },
  readMoreText: { color: COLORS.primary, fontSize: 13, fontWeight: "700" },

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
