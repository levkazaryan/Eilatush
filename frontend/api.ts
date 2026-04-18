import { Linking, Platform } from "react-native";
import * as WebBrowser from "expo-web-browser";

const API = process.env.EXPO_PUBLIC_BACKEND_URL;

export const api = {
  base: API,
  async events(params: { band?: string; category?: string } = {}) {
    const q = new URLSearchParams();
    if (params.band) q.set("band", params.band);
    if (params.category) q.set("category", params.category);
    const r = await fetch(`${API}/api/events?${q.toString()}`);
    return r.json();
  },
  async businesses(params: { category?: string; open_now?: boolean; q?: string } = {}) {
    const qs = new URLSearchParams();
    if (params.category) qs.set("category", params.category);
    if (params.open_now) qs.set("open_now", "true");
    if (params.q) qs.set("q", params.q);
    const r = await fetch(`${API}/api/businesses?${qs.toString()}`);
    return r.json();
  },
  async jobs(params: { urgency?: string; category?: string } = {}) {
    const qs = new URLSearchParams();
    if (params.urgency) qs.set("urgency", params.urgency);
    if (params.category) qs.set("category", params.category);
    const r = await fetch(`${API}/api/jobs?${qs.toString()}`);
    return r.json();
  },
  async news(params: { source?: string; source_name?: string } = {}) {
    const qs = new URLSearchParams();
    if (params.source) qs.set("source", params.source);
    if (params.source_name) qs.set("source_name", params.source_name);
    const r = await fetch(`${API}/api/news?${qs.toString()}`);
    return r.json();
  },
  async newsSources() {
    const r = await fetch(`${API}/api/news/sources`);
    return r.json();
  },
  async chat(message: string, session_id?: string) {
    const r = await fetch(`${API}/api/eilatush/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id }),
    });
    return r.json();
  },
};

export const openWhatsApp = (phone?: string, message?: string) => {
  if (!phone) return;
  const clean = phone.replace(/[^0-9+]/g, "");
  const text = encodeURIComponent(message || "");
  const url = `https://wa.me/${clean.replace(/^\+/, "")}?text=${text}`;
  Linking.openURL(url).catch(() => {});
};

export const openPhone = (phone?: string) => {
  if (!phone) return;
  const url = `tel:${phone}`;
  Linking.openURL(url).catch(() => {});
};

export const openLink = (url?: string) => {
  if (!url) return;
  if (Platform.OS === "web") {
    // Web: open in new tab (can't use CustomTabs/SFSafariViewController)
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  // Native: open in-app browser (SFSafariViewController on iOS, Chrome Custom Tabs on Android)
  WebBrowser.openBrowserAsync(url, {
    toolbarColor: "#E63946",
    controlsColor: "#FFFFFF",
    dismissButtonStyle: "close",
    readerMode: false,
    enableBarCollapsing: true,
    showTitle: true,
  }).catch(() => {
    // Fallback to system browser if WebBrowser fails
    Linking.openURL(url).catch(() => {});
  });
};

export const formatHebrewTime = (iso?: string | null): string => {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffMinAbs = Math.abs(diffMs) / 60000;
  const diffHrAbs = diffMinAbs / 60;
  const diffDayAbs = diffHrAbs / 24;
  const pad = (n: number) => n.toString().padStart(2, "0");
  const hhmm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;

  // Future (events): keep "עכשיו / היום HH:MM / מחר HH:MM / date"
  if (diffMs >= 0) {
    if (diffMinAbs < 60) return "עכשיו";
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return `היום ${hhmm}`;
    const tomorrow = new Date(now.getTime() + 86400000);
    if (d.toDateString() === tomorrow.toDateString()) return `מחר ${hhmm}`;
    return d.toLocaleString("he-IL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  // Past (news): relative for <1d, else actual date
  if (diffMinAbs < 60) {
    const m = Math.max(1, Math.round(diffMinAbs));
    return `לפני ${m} דק׳`;
  }
  if (diffHrAbs < 24) {
    const h = Math.max(1, Math.round(diffHrAbs));
    if (h === 1) return `לפני שעה`;
    if (h === 2) return `לפני שעתיים`;
    return `לפני ${h} שעות`;
  }
  if (diffDayAbs < 7) {
    const days = Math.floor(diffDayAbs);
    if (days === 1) return `אתמול`;
    if (days === 2) return `לפני יומיים`;
    return `לפני ${days} ימים`;
  }
  // older — show full date (dd/mm/yy)
  return d.toLocaleDateString("he-IL", { day: "2-digit", month: "2-digit", year: "2-digit" });
};

export const formatJobPosted = (iso: string): string => {
  const d = new Date(iso);
  const now = new Date();
  const diffMin = Math.round((now.getTime() - d.getTime()) / 60000);
  if (diffMin < 60) return `לפני ${diffMin} דק'`;
  if (diffMin < 1440) return `לפני ${Math.floor(diffMin / 60)} שע'`;
  return `לפני ${Math.floor(diffMin / 1440)} ימים`;
};

export const isWeb = Platform.OS === "web";
