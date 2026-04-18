import { Linking, Platform } from "react-native";

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
  async news(params: { source?: string } = {}) {
    const qs = new URLSearchParams();
    if (params.source) qs.set("source", params.source);
    const r = await fetch(`${API}/api/news?${qs.toString()}`);
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
  Linking.openURL(url).catch(() => {});
};

export const formatHebrewTime = (iso: string): string => {
  const d = new Date(iso);
  const now = new Date();
  const diffMin = Math.round((d.getTime() - now.getTime()) / 60000);
  if (diffMin >= -60 && diffMin <= 60) return "עכשיו";
  if (diffMin < 0 && diffMin > -1440) return "היום";
  const sameDay = d.toDateString() === now.toDateString();
  if (sameDay) {
    return `היום ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  }
  const tomorrow = new Date(now.getTime() + 86400000);
  if (d.toDateString() === tomorrow.toDateString()) {
    return `מחר ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`;
  }
  return d.toLocaleString("he-IL", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
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
