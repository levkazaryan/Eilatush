/**
 * Compares the installed app version against the latest published version
 * (read from /api/app-version) and decides whether to show the update modal.
 *
 *  • Soft update — `current < latest` (and not force) → dismissible banner
 *  • Force update — `current < min_required` OR `force === true` → blocking modal
 *  • Up-to-date  → nothing
 *
 * On web (where the user is browsing the preview) we always skip the check.
 */
import * as Application from "expo-application";
import { Linking, Platform } from "react-native";

export type RemoteVersionConfig = {
  latest_version: string;
  min_required_version: string;
  message: string;
  play_store_url: string;
  force: boolean;
};

export type UpdateDecision =
  | { kind: "none" }
  | { kind: "soft"; config: RemoteVersionConfig; current: string }
  | { kind: "force"; config: RemoteVersionConfig; current: string };

const FALLBACK_API = "https://eilat-connect.emergent.host";
const API_BASE: string =
  (process.env.EXPO_PUBLIC_BACKEND_URL || "").trim() || FALLBACK_API;

/** "1.2.3" → [1, 2, 3]; missing parts default to 0; non-numeric → 0. */
function parseVersion(v: string | null | undefined): number[] {
  if (!v) return [0, 0, 0];
  const parts = String(v).trim().split(".").map((p) => {
    const n = parseInt(p, 10);
    return Number.isFinite(n) ? n : 0;
  });
  while (parts.length < 3) parts.push(0);
  return parts.slice(0, 3);
}

/** Returns true if `a < b`. Versions like "1.2.3". */
function isLessThan(a: string, b: string): boolean {
  const av = parseVersion(a);
  const bv = parseVersion(b);
  for (let i = 0; i < 3; i++) {
    if (av[i] !== bv[i]) return av[i] < bv[i];
  }
  return false;
}

/** Read installed version from the native bundle (Expo). */
export function getCurrentVersion(): string {
  // nativeApplicationVersion = "1.0.1" on Android/iOS; null on web/Expo Go web.
  return Application.nativeApplicationVersion ?? "0.0.0";
}

export async function checkForUpdate(): Promise<UpdateDecision> {
  // Skip on web — there's no Play Store there
  if (Platform.OS === "web") return { kind: "none" };
  if (!API_BASE) return { kind: "none" };

  let config: RemoteVersionConfig;
  try {
    const res = await fetch(`${API_BASE}/api/app-version`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return { kind: "none" };
    config = (await res.json()) as RemoteVersionConfig;
  } catch (e) {
    // Network / DNS / backend down → never block the user
    return { kind: "none" };
  }

  const current = getCurrentVersion();

  // Force update — strict
  if (config.force === true || isLessThan(current, config.min_required_version)) {
    return { kind: "force", config, current };
  }
  // Soft update — friendly suggestion
  if (isLessThan(current, config.latest_version)) {
    return { kind: "soft", config, current };
  }
  return { kind: "none" };
}

/** Open the Google Play page for this app. Falls back to the web URL if the
 * native Play Store app isn't installed (rare on real devices). */
export async function openPlayStore(url: string): Promise<void> {
  // Native intent — opens the Play Store app directly when installed.
  const nativeIntent = "market://details?id=app.eilatush";
  try {
    const supported = await Linking.canOpenURL(nativeIntent);
    if (supported) {
      await Linking.openURL(nativeIntent);
      return;
    }
  } catch {
    // fallthrough
  }
  try {
    await Linking.openURL(url);
  } catch (e) {
    console.warn("openPlayStore failed", e);
  }
}
