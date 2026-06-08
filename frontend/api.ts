import { Linking, Platform } from "react-native";
import * as WebBrowser from "expo-web-browser";

// Resolve the backend URL with a hard-coded fallback.
//
// Why the fallback?  EAS build env-vars can silently fail to inject for a
// number of reasons (cached builds, wrong eas-cli version, profile mix-ups).
// If `EXPO_PUBLIC_BACKEND_URL` ever ends up undefined or empty, EVERY API call
// would go to `undefined/api/...` and the app would look broken (empty lists
// on every tab) — even though the backend is perfectly healthy.
//
// Production deployment URL is fixed for this app, so we use it as a safe
// default. The env var still wins when set — useful for dev / preview builds.
const FALLBACK_API = "https://eilat-connect.emergent.host";
const API: string = (process.env.EXPO_PUBLIC_BACKEND_URL || "").trim() || FALLBACK_API;

export const api = {
  base: API,
  async events(params: { band?: string; category?: string; date?: string } = {}) {
    const q = new URLSearchParams();
    if (params.band) q.set("band", params.band);
    if (params.category) q.set("category", params.category);
    if (params.date) q.set("date", params.date);
    const r = await fetch(`${API}/api/events?${q.toString()}`);
    return r.json();
  },
  async eventDays() {
    const r = await fetch(`${API}/api/events/days`);
    if (!r.ok) return [];
    return r.json();
  },
  async businesses(params: {
    type?: "business" | "professional";
    category?: string[] | string;
    source?: string[] | string;
    q?: string;
    open_now?: boolean;
    limit?: number;
  } = {}) {
    const qs = new URLSearchParams();
    const toParam = (v?: string[] | string) => {
      if (!v) return undefined;
      if (Array.isArray(v)) return v.length ? v.join(",") : undefined;
      return v || undefined;
    };
    if (params.type) qs.set("type", params.type);
    const c = toParam(params.category); if (c) qs.set("category", c);
    const s = toParam(params.source); if (s) qs.set("source", s);
    if (params.q) qs.set("q", params.q);
    if (params.open_now) qs.set("open_now", "true");
    if (params.limit) qs.set("limit", String(params.limit));
    const r = await fetch(`${API}/api/businesses?${qs.toString()}`);
    return r.json();
  },
  async businessesCategories(type: "business" | "professional" = "business") {
    const r = await fetch(`${API}/api/businesses/categories?type=${type}`);
    return r.json();
  },
  async businessesSources(type: "business" | "professional" = "business") {
    const r = await fetch(`${API}/api/businesses/sources?type=${type}`);
    return r.json();
  },
  async businessesStatus() {
    const r = await fetch(`${API}/api/businesses/status`);
    return r.json();
  },
  async business(id: string) {
    const r = await fetch(`${API}/api/businesses/${id}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
  async jobs(params: {
    urgency?: string;
    category?: string[] | string;
    date_range?: string;
    job_type?: string[] | string;
    experience?: string[] | string;
    source?: string[] | string;
  } = {}) {
    const qs = new URLSearchParams();
    const toParam = (v?: string[] | string) => {
      if (!v) return undefined;
      if (Array.isArray(v)) return v.length ? v.join(",") : undefined;
      return v || undefined;
    };
    if (params.urgency) qs.set("urgency", params.urgency);
    const c = toParam(params.category); if (c) qs.set("category", c);
    if (params.date_range) qs.set("date_range", params.date_range);
    const jt = toParam(params.job_type); if (jt) qs.set("job_type", jt);
    const ex = toParam(params.experience); if (ex) qs.set("experience", ex);
    const src = toParam(params.source); if (src) qs.set("source", src);
    const r = await fetch(`${API}/api/jobs?${qs.toString()}`);
    return r.json();
  },
  async jobsCategories() {
    const r = await fetch(`${API}/api/jobs/categories`);
    return r.json();
  },
  async jobsSources() {
    const r = await fetch(`${API}/api/jobs/sources`);
    return r.json();
  },
  async jobsStatus() {
    const r = await fetch(`${API}/api/jobs/status`);
    return r.json();
  },
  async job(id: string) {
    const r = await fetch(`${API}/api/jobs/${id}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
  async news(params: { source?: string; source_name?: string; category?: string } = {}) {
    const qs = new URLSearchParams();
    if (params.source) qs.set("source", params.source);
    if (params.source_name) qs.set("source_name", params.source_name);
    if (params.category) qs.set("category", params.category);
    const r = await fetch(`${API}/api/news?${qs.toString()}`);
    return r.json();
  },
  async newsSources() {
    const r = await fetch(`${API}/api/news/sources`);
    return r.json();
  },
  async newsCategories() {
    const r = await fetch(`${API}/api/news/categories`);
    return r.json();
  },
  async newsStatus() {
    const r = await fetch(`${API}/api/news/status`);
    return r.json();
  },
  async chat(
    message: string,
    session_id?: string,
    history?: { role: string; text: string }[],
    user_gender?: "m" | "f",
  ) {
    const r = await fetch(`${API}/api/eilatush/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id, history, user_gender }),
    });
    return r.json();
  },

  /**
   * Streaming version of chat. Calls onMeta/onToken/onDone/onError as SSE events arrive.
   * Returns a cancel function that aborts the stream when called.
   * Falls back to the non-streaming endpoint if streaming isn't supported on this platform.
   */
  chatStream(
    message: string,
    handlers: {
      onMeta?: (meta: any) => void;
      onToken?: (text: string) => void;
      onDone?: (data: any) => void;
      onError?: (err: any) => void;
    },
    opts?: {
      session_id?: string;
      history?: { role: string; text: string }[];
      user_gender?: "m" | "f";
    },
  ): () => void {
    let cancelled = false;
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;

    const fallback = async () => {
      try {
        const res = await fetch(`${API}/api/eilatush/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message,
            session_id: opts?.session_id,
            history: opts?.history,
            user_gender: opts?.user_gender,
          }),
        });
        const j = await res.json();
        if (cancelled) return;
        handlers.onMeta?.({
          session_id: j.session_id,
          intent: j.intent,
          results: j.results,
          weather: j.weather,
        });
        handlers.onToken?.(j.reply || "");
        handlers.onDone?.({ reply: j.reply, follow_ups: j.follow_ups });
      } catch (e) {
        if (!cancelled) handlers.onError?.(e);
      }
    };

    (async () => {
      try {
        const res = await fetch(`${API}/api/eilatush/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({
            message,
            session_id: opts?.session_id,
            history: opts?.history,
            user_gender: opts?.user_gender,
          }),
          signal: controller?.signal,
        });

        // Detect whether we can read the body as a stream
        // @ts-ignore — getReader is only on web's ReadableStream
        const reader = res.body && typeof res.body.getReader === "function" ? res.body.getReader() : null;
        if (!reader) {
          // React Native fetch does not support streaming reader → fallback
          console.log("[chatStream] no reader available — falling back to non-streaming");
          await fallback();
          return;
        }

        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        // eslint-disable-next-line no-constant-condition
        while (true) {
          if (cancelled) {
            try {
              await reader.cancel();
            } catch (_) {}
            return;
          }
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          // SSE events are separated by blank lines (\n\n)
          let sep;
          while ((sep = buffer.indexOf("\n\n")) !== -1) {
            const rawEvent = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            const lines = rawEvent.split("\n");
            let eventName = "message";
            let dataLines: string[] = [];
            for (const ln of lines) {
              if (ln.startsWith("event:")) eventName = ln.slice(6).trim();
              else if (ln.startsWith("data:")) dataLines.push(ln.slice(5).trimStart());
            }
            const dataStr = dataLines.join("\n");
            if (!dataStr) continue;
            let payload: any = null;
            try {
              payload = JSON.parse(dataStr);
            } catch {
              continue;
            }
            if (eventName === "meta") handlers.onMeta?.(payload);
            else if (eventName === "token") handlers.onToken?.(payload?.text || "");
            else if (eventName === "done") handlers.onDone?.(payload);
            else if (eventName === "error") handlers.onError?.(payload);
          }
        }
      } catch (e: any) {
        if (cancelled) return;
        // Streaming failed → try non-streaming fallback
        console.warn("[chatStream] stream error, falling back:", e?.message || e);
        await fallback();
      }
    })();

    return () => {
      cancelled = true;
      try {
        controller?.abort();
      } catch (_) {}
    };
  },
};

export const openWaze = (query?: string) => {
  if (!query) return;
  // Opens Waze search; when address is given, Waze picks the best match.
  const encoded = encodeURIComponent(query);
  const url = `https://waze.com/ul?q=${encoded}&navigate=yes`;
  Linking.openURL(url).catch(() => {});
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

/**
 * Format a stored phone (+972xxxxxxxx / 972xxxxxxxx) to the local Israeli
 * display format with a leading "0" (e.g. "+972535319943" → "0535319943").
 * Falls back to the raw string if the input is not an Israeli number.
 */
export const displayPhone = (phone?: string | null): string => {
  if (!phone) return "";
  const s = String(phone).trim();
  if (s.startsWith("+972")) return "0" + s.slice(4);
  if (s.startsWith("972")) return "0" + s.slice(3);
  return s;
};

export const openEmail = (email?: string, subject?: string, body?: string) => {
  if (!email) return;
  const params: string[] = [];
  if (subject) params.push(`subject=${encodeURIComponent(subject)}`);
  if (body) params.push(`body=${encodeURIComponent(body)}`);
  const url = `mailto:${email}${params.length ? "?" + params.join("&") : ""}`;
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

// ---------------------------------------------------------------------------
// App-wide share + contact helpers
// ---------------------------------------------------------------------------
export const CONTACT_PHONE = "972535319943";
export const APP_URL =
  (typeof process !== "undefined" && process.env?.EXPO_PUBLIC_APP_URL) ||
  "https://eilatush.app";
export const SHARE_MSG = `היי 👋
גיליתי את אילתוש 🐠 - אפליקציה שמרכזת הכל על אילת:
אירועים, עסקים, עבודה, חדשות ואיש קשר חכם שיודע הכל על העיר.
שווה לבדוק:
${APP_URL}`;

export async function openContactWhatsApp() {
  const text = encodeURIComponent(
    "היי, הגעתי מהאפליקציה אילתוש. אשמח לעזרה / פידבק 🙂",
  );
  const appUrl = `whatsapp://send?phone=${CONTACT_PHONE}&text=${text}`;
  const webUrl = `https://wa.me/${CONTACT_PHONE}?text=${text}`;
  try {
    if (Platform.OS === "web") {
      await Linking.openURL(webUrl);
      return;
    }
    const canApp = await Linking.canOpenURL(appUrl);
    await Linking.openURL(canApp ? appUrl : webUrl);
  } catch {
    try {
      await Linking.openURL(webUrl);
    } catch {
      /* silent */
    }
  }
}

export async function shareApp() {
  try {
    if (Platform.OS === "web") {
      const nav: any = (globalThis as any).navigator;
      if (nav?.share) {
        await nav.share({ title: "אילתוש 🐠", text: SHARE_MSG, url: APP_URL });
        return;
      }
      if (nav?.clipboard?.writeText) {
        await nav.clipboard.writeText(SHARE_MSG);
        return;
      }
    }
    const { Share } = await import("react-native");
    await Share.share({ message: SHARE_MSG, url: APP_URL, title: "אילתוש 🐠" });
  } catch {
    /* user cancelled — silent */
  }
}

export const formatHebrewTime = (iso?: string | null): string => {
  if (!iso) return "";
  // Backend stores UTC. If the ISO string lacks a timezone suffix, append "Z"
  // so JS parses it as UTC (not local time), otherwise the "time ago" will
  // drift by the local timezone offset (2-3 hours off in Israel).
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + "Z";
  const d = new Date(normalized);
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

// ---------------------------------------------------------------------------
// VIP Membership API (תושב אילת VIP)
// ---------------------------------------------------------------------------
export type VIPMember = {
  id: string;
  full_name: string;
  email: string;
  phone: string;
  dob: string;
  address: string;
  member_number: string;
  join_date: string;
  expiry_date: string;
  is_active: boolean;
};

export type VIPDiscount = {
  id: string;
  place: string;
  business_name: string;
  gift_text: string;
  age_restriction?: string | null;
  category?: string | null;
  image_url?: string | null;
  order: number;
  active: boolean;
};

export type VIPAuthResponse = { token: string; member: VIPMember };

async function vipFetch(path: string, init: RequestInit = {}, token?: string | null) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((init.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API}/api/vip${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const j = await res.json();
      detail = j?.detail || detail;
    } catch {
      // ignore
    }
    const err: any = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export const vipApi = {
  async teaser(): Promise<{ discount_count: number }> {
    return vipFetch("/teaser", { method: "GET" });
  },
  async register(payload: {
    full_name: string;
    email: string;
    phone: string;
    dob: string;
    address: string;
  }): Promise<VIPAuthResponse> {
    return vipFetch("/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  async login(payload: { phone: string; dob: string }): Promise<VIPAuthResponse> {
    return vipFetch("/login", { method: "POST", body: JSON.stringify(payload) });
  },
  async me(token: string): Promise<VIPMember> {
    return vipFetch("/me", { method: "GET" }, token);
  },
  async discounts(token: string): Promise<VIPDiscount[]> {
    return vipFetch("/discounts", { method: "GET" }, token);
  },
};
