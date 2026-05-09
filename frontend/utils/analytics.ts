/**
 * Lightweight analytics client for Eilatush.
 *
 * Generates an anonymous user_id on first launch (stored in AsyncStorage)
 * and provides a fire-and-forget `track()` helper used throughout the app.
 *
 * Events sent here surface in the admin chat ("תני לי סטטיסטיקה") and the
 * branded PDF report.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";

const STORAGE_KEY = "eilatush.anon_user_id";
const BACKEND =
  (typeof process !== "undefined" && process.env?.EXPO_PUBLIC_BACKEND_URL) ||
  "https://eilat-connect.emergent.host";

let _userIdCache: string | null = null;
let _resolvingUserId: Promise<string> | null = null;

function _newAnonId(): string {
  // ~92 bits of entropy; collision risk is negligible for this scale.
  return (
    "anon_" +
    Math.random().toString(36).slice(2, 10) +
    Math.random().toString(36).slice(2, 10)
  );
}

export async function getUserId(): Promise<string> {
  if (_userIdCache) return _userIdCache;
  if (_resolvingUserId) return _resolvingUserId;
  _resolvingUserId = (async () => {
    try {
      const existing = await AsyncStorage.getItem(STORAGE_KEY);
      if (existing && existing.length > 5) {
        _userIdCache = existing;
        return existing;
      }
    } catch {}
    const id = _newAnonId();
    try {
      await AsyncStorage.setItem(STORAGE_KEY, id);
    } catch {}
    _userIdCache = id;
    return id;
  })();
  return _resolvingUserId;
}

export type AnalyticsEvent =
  | "app_open"
  | "screen_view"
  | "business_view"
  | "business_phone_click"
  | "business_directions_click"
  | "business_website_click"
  | "job_view"
  | "job_outbound_click"
  | "event_view"
  | "event_outbound_click"
  | "news_view"
  | "news_outbound_click"
  | "ai_message";

export async function track(
  event: AnalyticsEvent,
  props: Record<string, any> = {}
): Promise<void> {
  try {
    const user_id = await getUserId();
    // Fire and forget — never block UI on analytics
    fetch(`${BACKEND}/api/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id, event, props }),
    }).catch(() => {});
  } catch {
    /* swallow */
  }
}

// Convenience wrappers ------------------------------------------------------
export const trackScreen = (screen: string) =>
  track("screen_view", { screen });

export const trackBusinessView = (id: string, name?: string) =>
  track("business_view", { id, name });

export const trackBusinessPhone = (id: string) =>
  track("business_phone_click", { id });

export const trackBusinessDirections = (id: string) =>
  track("business_directions_click", { id });

export const trackBusinessWebsite = (id: string) =>
  track("business_website_click", { id });

export const trackJobView = (id: string, title?: string) =>
  track("job_view", { id, title });

export const trackJobOutbound = (id: string) =>
  track("job_outbound_click", { id });

export const trackEventView = (id: string, title?: string) =>
  track("event_view", { id, title });

export const trackEventOutbound = (id: string) =>
  track("event_outbound_click", { id });

export const trackNewsView = (id: string, title?: string) =>
  track("news_view", { id, title });

export const trackNewsOutbound = (id: string) =>
  track("news_outbound_click", { id });

export const trackAppOpen = () => track("app_open", {});
