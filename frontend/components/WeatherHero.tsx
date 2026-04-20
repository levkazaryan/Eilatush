'use client';

import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Modal,
  ScrollView,
  ActivityIndicator,
  Dimensions,
} from "react-native";
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  withSequence,
  Easing,
} from "react-native-reanimated";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { COLORS, RADIUS, SPACING } from "../theme";
import { shareApp, openContactWhatsApp } from "../api";

// ---------------------------------------------------------------------------
// Weather helpers
// ---------------------------------------------------------------------------
type Current = {
  temperature: number;
  weatherCode: number;
  isDay: boolean;
};
type DailyItem = {
  date: string;          // ISO yyyy-mm-dd
  max: number;
  min: number;
  weatherCode: number;
  sunrise: string;
  sunset: string;
};
type WeatherData = {
  current: Current;
  daily: DailyItem[];
};

const EILAT_LAT = 29.5577;
const EILAT_LON = 34.9519;
const API_URL =
  `https://api.open-meteo.com/v1/forecast?latitude=${EILAT_LAT}&longitude=${EILAT_LON}` +
  `&current=temperature_2m,weather_code,is_day` +
  `&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset` +
  `&timezone=auto&forecast_days=7`;

/** WMO weather codes → Hebrew label + Ionicon */
function wmoMeta(code: number, isDay = true): { label: string; icon: keyof typeof Ionicons.glyphMap; color: string } {
  if (code === 0) return { label: "בהיר", icon: isDay ? "sunny" : "moon", color: isDay ? "#FCD34D" : "#E5E7EB" };
  if (code <= 2) return { label: "מעונן חלקית", icon: isDay ? "partly-sunny" : "cloudy-night", color: "#FBBF24" };
  if (code === 3) return { label: "מעונן", icon: "cloudy", color: "#9CA3AF" };
  if (code >= 45 && code <= 48) return { label: "ערפל", icon: "cloud", color: "#9CA3AF" };
  if (code >= 51 && code <= 57) return { label: "טפטוף", icon: "rainy", color: "#60A5FA" };
  if (code >= 61 && code <= 67) return { label: "גשם", icon: "rainy", color: "#3B82F6" };
  if (code >= 71 && code <= 77) return { label: "שלג", icon: "snow", color: "#BFDBFE" };
  if (code >= 80 && code <= 82) return { label: "ממטרים", icon: "thunderstorm", color: "#2563EB" };
  if (code >= 95) return { label: "סופה", icon: "thunderstorm", color: "#4338CA" };
  return { label: "—", icon: "help-circle", color: "#94A3B8" };
}

const DAY_NAMES = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
function dayLabel(iso: string, index: number): string {
  if (index === 0) return "היום";
  if (index === 1) return "מחר";
  const d = new Date(iso + "T12:00:00");
  return DAY_NAMES[d.getDay()];
}

/** Sky gradient colors based on local hour (0–23). */
function skyColors(hour: number): readonly [string, string, string] {
  // Night (22–4)
  if (hour >= 22 || hour < 5) return ["#0B1026", "#1E1B4B", "#312E81"] as const;
  // Sunrise (5–7)
  if (hour < 7) return ["#1E293B", "#7C3AED", "#F59E0B"] as const;
  // Morning (7–11)
  if (hour < 11) return ["#38BDF8", "#60A5FA", "#FCD34D"] as const;
  // Midday (11–16)
  if (hour < 16) return ["#0EA5E9", "#38BDF8", "#FDE68A"] as const;
  // Afternoon (16–18)
  if (hour < 18) return ["#0284C7", "#F59E0B", "#FB923C"] as const;
  // Sunset (18–20)
  if (hour < 20) return ["#1E293B", "#BE185D", "#F97316"] as const;
  // Dusk (20–22)
  return ["#0F172A", "#312E81", "#BE185D"] as const;
}

// ---------------------------------------------------------------------------
// Animated sun / moon
// ---------------------------------------------------------------------------
function FloatingOrb({ isDay }: { isDay: boolean }) {
  const translateY = useSharedValue(0);
  const rotate = useSharedValue(0);
  const glow = useSharedValue(0.6);

  useEffect(() => {
    translateY.value = withRepeat(
      withSequence(
        withTiming(-8, { duration: 3000, easing: Easing.inOut(Easing.ease) }),
        withTiming(8, { duration: 3000, easing: Easing.inOut(Easing.ease) }),
      ),
      -1,
      true,
    );
    rotate.value = withRepeat(
      withTiming(360, { duration: 60000, easing: Easing.linear }),
      -1,
      false,
    );
    glow.value = withRepeat(
      withSequence(
        withTiming(1, { duration: 2500, easing: Easing.inOut(Easing.ease) }),
        withTiming(0.6, { duration: 2500, easing: Easing.inOut(Easing.ease) }),
      ),
      -1,
      true,
    );
  }, []);

  const orbStyle = useAnimatedStyle(() => ({
    transform: [
      { translateY: translateY.value },
      { rotate: `${rotate.value}deg` },
    ],
  }));
  const glowStyle = useAnimatedStyle(() => ({
    opacity: glow.value,
    transform: [{ scale: 0.9 + glow.value * 0.25 }],
  }));

  return (
    <View style={styles.orbContainer}>
      <Animated.View style={[styles.orbGlow, isDay ? styles.sunGlow : styles.moonGlow, glowStyle]} />
      <Animated.View style={[styles.orb, orbStyle]}>
        <Ionicons
          name={isDay ? "sunny" : "moon"}
          size={58}
          color={isDay ? "#FBBF24" : "#E5E7EB"}
        />
      </Animated.View>
    </View>
  );
}

function DriftingCloud({
  delay,
  top,
  size,
  opacity,
}: { delay: number; top: number; size: number; opacity: number }) {
  const x = useSharedValue(-200);
  const W = Dimensions.get("window").width;

  useEffect(() => {
    const run = () => {
      x.value = -size;
      x.value = withTiming(W + size, {
        duration: 40000 + delay * 1000,
        easing: Easing.linear,
      });
    };
    run();
    const id = setInterval(run, 40000 + delay * 1000);
    return () => clearInterval(id);
  }, []);

  const style = useAnimatedStyle(() => ({
    transform: [{ translateX: x.value }],
    opacity,
  }));
  return (
    <Animated.View style={[styles.cloud, { top, width: size, height: size * 0.45 }, style]} />
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function WeatherHero({
  title,
  subtitle,
  brand,
  rightSlot,
  showActions = true,
}: {
  title: string;
  subtitle?: string;
  brand?: React.ReactNode;
  rightSlot?: React.ReactNode;
  /** Show the share + WhatsApp contact buttons in the header */
  showActions?: boolean;
}) {
  const [data, setData] = useState<WeatherData | null>(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [hour, setHour] = useState(new Date().getHours());

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const r = await fetch(API_URL);
        const j = await r.json();
        if (!mounted) return;
        const current: Current = {
          temperature: Math.round(j?.current?.temperature_2m ?? 0),
          weatherCode: j?.current?.weather_code ?? 0,
          isDay: j?.current?.is_day === 1,
        };
        const daily: DailyItem[] = (j?.daily?.time || []).map((t: string, i: number) => ({
          date: t,
          max: Math.round(j.daily.temperature_2m_max[i]),
          min: Math.round(j.daily.temperature_2m_min[i]),
          weatherCode: j.daily.weather_code[i],
          sunrise: j.daily.sunrise[i],
          sunset: j.daily.sunset[i],
        }));
        setData({ current, daily });
      } catch (e) {
        // silent – widget just won't show weather
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // Recompute sky gradient every 10 minutes
  useEffect(() => {
    const id = setInterval(() => setHour(new Date().getHours()), 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const isDay = useMemo(() => data?.current.isDay ?? (hour >= 6 && hour < 19), [data, hour]);
  const colors = useMemo(() => skyColors(hour), [hour]);
  const meta = data ? wmoMeta(data.current.weatherCode, isDay) : null;

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={colors as any}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      {/* Stars (night only) */}
      {!isDay ? (
        <>
          <View style={[styles.star, { top: 28,  left: "18%", width: 2, height: 2 }]} />
          <View style={[styles.star, { top: 58,  left: "42%", width: 3, height: 3 }]} />
          <View style={[styles.star, { top: 96,  left: "72%", width: 2, height: 2 }]} />
          <View style={[styles.star, { top: 22,  left: "82%", width: 3, height: 3, opacity: 0.7 }]} />
          <View style={[styles.star, { top: 140, left: "28%", width: 2, height: 2, opacity: 0.6 }]} />
          <View style={[styles.star, { top: 170, left: "58%", width: 3, height: 3 }]} />
        </>
      ) : null}
      {/* Drifting clouds (day only) */}
      {isDay ? (
        <>
          <DriftingCloud delay={0}  top={40}  size={140} opacity={0.55} />
          <DriftingCloud delay={8}  top={90}  size={100} opacity={0.38} />
          <DriftingCloud delay={16} top={150} size={160} opacity={0.30} />
        </>
      ) : null}

      {/* Sun/Moon */}
      <FloatingOrb isDay={isDay} />

      {/* Soft dark overlay to keep text readable */}
      <View style={styles.dim} />

      {/* Content */}
      <View style={styles.content}>
        {brand}
        <Text style={styles.title}>{title}</Text>
        {subtitle ? <Text style={styles.sub}>{subtitle}</Text> : null}
      </View>

      {/* Weather pill – top start (right in RTL) */}
      <Pressable
        onPress={() => data && setModalOpen(true)}
        style={({ pressed }) => [styles.pill, pressed && { opacity: 0.75 }]}
        testID="weather-pill"
      >
        {loading ? (
          <ActivityIndicator size="small" color="#fff" />
        ) : data && meta ? (
          <>
            <Ionicons name={meta.icon} size={22} color={meta.color} />
            <Text style={styles.pillTemp}>{data.current.temperature}°</Text>
            <Text style={styles.pillLabel}>{meta.label}</Text>
            <Ionicons name="chevron-back" size={14} color="rgba(255,255,255,0.8)" />
          </>
        ) : null}
      </Pressable>

      {/* Action buttons – top left: share + WhatsApp contact */}
      {showActions ? (
        <View style={styles.headerActions}>
          <Pressable
            onPress={shareApp}
            style={({ pressed }) => [
              styles.headerIconBtn,
              pressed && { opacity: 0.7 },
            ]}
            accessibilityLabel="הזמן חבר"
            testID="hero-invite"
          >
            <Ionicons name="share-social-outline" size={20} color="#fff" />
          </Pressable>
          <Pressable
            onPress={openContactWhatsApp}
            style={({ pressed }) => [
              styles.headerIconBtn,
              { backgroundColor: "#25D366", borderColor: "rgba(255,255,255,0.6)" },
              pressed && { opacity: 0.8 },
            ]}
            accessibilityLabel="צור קשר בוואטסאפ"
            testID="hero-contact"
          >
            <Ionicons name="logo-whatsapp" size={20} color="#fff" />
          </Pressable>
        </View>
      ) : null}

      {/* 7-day modal */}
      <Modal
        visible={modalOpen}
        transparent
        animationType="slide"
        onRequestClose={() => setModalOpen(false)}
      >
        <Pressable style={styles.modalBackdrop} onPress={() => setModalOpen(false)}>
          <Pressable style={styles.modalSheet} onPress={(e) => e.stopPropagation()}>
            <View style={styles.modalHandle} />
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>מזג אוויר באילת · 7 ימים</Text>
              <Pressable onPress={() => setModalOpen(false)} hitSlop={10}>
                <Ionicons name="close" size={24} color={COLORS.textPrimary} />
              </Pressable>
            </View>
            <ScrollView>
              {(data?.daily || []).map((d, i) => {
                const m = wmoMeta(d.weatherCode, true);
                return (
                  <View key={d.date} style={styles.forecastRow}>
                    <View style={styles.forecastDayBox}>
                      <Text style={styles.forecastDay}>{dayLabel(d.date, i)}</Text>
                      <Text style={styles.forecastDate}>{d.date.slice(5).replace("-", "/")}</Text>
                    </View>
                    <View style={styles.forecastIconBox}>
                      <Ionicons name={m.icon} size={26} color={m.color} />
                      <Text style={styles.forecastLabel}>{m.label}</Text>
                    </View>
                    <View style={styles.forecastTempBox}>
                      <Text style={styles.forecastMax}>{d.max}°</Text>
                      <Text style={styles.forecastMin}>{d.min}°</Text>
                    </View>
                  </View>
                );
              })}
              {data?.daily?.[0] ? (
                <View style={styles.sunBox}>
                  <View style={styles.sunItem}>
                    <Ionicons name="sunny" size={18} color="#FBBF24" />
                    <Text style={styles.sunLabel}>זריחה</Text>
                    <Text style={styles.sunTime}>
                      {data.daily[0].sunrise.slice(11, 16)}
                    </Text>
                  </View>
                  <View style={styles.sunDivider} />
                  <View style={styles.sunItem}>
                    <Ionicons name="moon" size={18} color="#A78BFA" />
                    <Text style={styles.sunLabel}>שקיעה</Text>
                    <Text style={styles.sunTime}>
                      {data.daily[0].sunset.slice(11, 16)}
                    </Text>
                  </View>
                </View>
              ) : null}
              <Text style={styles.attribution}>נתונים: open-meteo.com</Text>
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    height: 240,
    overflow: "hidden",
    justifyContent: "flex-end",
  },
  dim: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(12,12,18,0.35)",
  },
  content: {
    padding: SPACING.lg,
    zIndex: 2,
  },
  title: {
    color: "#fff",
    fontSize: 30,
    fontWeight: "900",
    textAlign: "right",
    writingDirection: "rtl",
    textShadowColor: "rgba(0,0,0,0.35)",
    textShadowRadius: 8,
  },
  sub: {
    color: "#fff",
    fontSize: 14,
    marginTop: 6,
    textAlign: "right",
    writingDirection: "rtl",
    opacity: 0.9,
  },

  pill: {
    position: "absolute",
    top: SPACING.md,
    right: SPACING.md, // RTL = visual right (and on LTR it also lives on right)
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 6,
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(255,255,255,0.18)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    zIndex: 5,
  },
  pillTemp: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "900",
  },
  pillLabel: {
    color: "#fff",
    fontSize: 12,
    opacity: 0.9,
    maxWidth: 80,
  },

  headerActions: {
    position: "absolute",
    top: SPACING.md,
    left: SPACING.md,
    flexDirection: "row",
    gap: 8,
    zIndex: 5,
  },
  headerIconBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(255,255,255,0.22)",
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.45)",
  },

  // orb
  orbContainer: {
    position: "absolute",
    top: 30,
    left: 28,
    width: 90,
    height: 90,
    alignItems: "center",
    justifyContent: "center",
  },
  orb: {
    width: 70,
    height: 70,
    alignItems: "center",
    justifyContent: "center",
  },
  orbGlow: {
    position: "absolute",
    width: 110,
    height: 110,
    borderRadius: 55,
  },
  sunGlow: {
    backgroundColor: "rgba(251,191,36,0.35)",
    shadowColor: "#FBBF24",
    shadowOpacity: 0.9,
    shadowRadius: 30,
    shadowOffset: { width: 0, height: 0 },
  },
  moonGlow: {
    backgroundColor: "rgba(199,210,254,0.25)",
    shadowColor: "#E5E7EB",
    shadowOpacity: 0.6,
    shadowRadius: 20,
    shadowOffset: { width: 0, height: 0 },
  },

  // clouds
  cloud: {
    position: "absolute",
    backgroundColor: "rgba(255,255,255,0.55)",
    borderRadius: 999,
  },
  star: {
    position: "absolute",
    backgroundColor: "#fff",
    borderRadius: 2,
    opacity: 0.85,
  },

  // modal
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(12,12,18,0.45)",
    justifyContent: "flex-end",
  },
  modalSheet: {
    backgroundColor: COLORS.bg,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: SPACING.md,
    paddingTop: 10,
    paddingBottom: SPACING.lg + 10,
    maxHeight: "85%",
  },
  modalHandle: {
    alignSelf: "center",
    width: 44,
    height: 4,
    borderRadius: 2,
    backgroundColor: COLORS.border,
    marginBottom: 10,
  },
  modalHeader: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 6,
    marginBottom: 6,
  },
  modalTitle: { fontSize: 17, fontWeight: "900", color: COLORS.textPrimary, textAlign: "right" },
  forecastRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    paddingVertical: 14,
    paddingHorizontal: 4,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    gap: 10,
  },
  forecastDayBox: { width: 78, alignItems: "flex-end" },
  forecastDay: { fontSize: 15, fontWeight: "800", color: COLORS.textPrimary, textAlign: "right" },
  forecastDate: { fontSize: 11, color: COLORS.textMuted, textAlign: "right", marginTop: 2 },
  forecastIconBox: { flex: 1, flexDirection: "row-reverse", alignItems: "center", gap: 8 },
  forecastLabel: { fontSize: 13, color: COLORS.textSecondary, textAlign: "right" },
  forecastTempBox: { flexDirection: "row-reverse", alignItems: "baseline", gap: 8 },
  forecastMax: { fontSize: 16, fontWeight: "900", color: COLORS.textPrimary },
  forecastMin: { fontSize: 14, color: COLORS.textMuted },
  sunBox: {
    flexDirection: "row-reverse",
    backgroundColor: COLORS.card,
    borderRadius: RADIUS.md,
    marginTop: SPACING.md,
    paddingVertical: 12,
  },
  sunItem: { flex: 1, alignItems: "center", gap: 4 },
  sunLabel: { fontSize: 12, color: COLORS.textMuted },
  sunTime: { fontSize: 15, fontWeight: "800", color: COLORS.textPrimary },
  sunDivider: { width: 1, backgroundColor: COLORS.border },
  attribution: { fontSize: 11, color: COLORS.textMuted, textAlign: "center", marginTop: 14 },
});
