import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Image,
  Platform,
} from "react-native";
import { COLORS, RADIUS, SPACING, SHADOWS } from "../theme";

const MASCOT = require("../assets/images/eilatush-mascot.png");
const DISMISS_KEY = "eilatush_pwa_install_dismissed_until";

/**
 * Web-only install banner — shown to mobile-web visitors who haven't yet
 * installed the PWA.  Slides up from the bottom of the screen with a friendly
 * Hebrew CTA + the actual `beforeinstallprompt` event triggered on Android.
 * On iOS Safari (no auto-prompt API), it gives manual instructions instead.
 *
 * Dismissal is remembered in localStorage for 14 days so we don't nag.
 */
export default function PWAInstallBanner() {
  const [visible, setVisible] = useState(false);
  const [hasNativePrompt, setHasNativePrompt] = useState(false);
  const [showIOSHelp, setShowIOSHelp] = useState(false);

  useEffect(() => {
    if (Platform.OS !== "web") return;
    if (typeof window === "undefined") return;

    // ── Don't show if already installed (display-mode: standalone) ────────
    const isStandalone =
      window.matchMedia?.("(display-mode: standalone)")?.matches ||
      // iOS Safari uses navigator.standalone
      (window.navigator as any).standalone === true;
    if (isStandalone) return;

    // ── Respect dismissal cooldown ────────────────────────────────────────
    try {
      const until = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
      if (until && Date.now() < until) return;
    } catch (_) {
      /* localStorage blocked → just continue */
    }

    // ── If already flagged as installed in localStorage ───────────────────
    try {
      if (localStorage.getItem("eilatush_pwa_installed") === "1") return;
    } catch (_) {}

    // ── Detect mobile (banner is mobile-only) ─────────────────────────────
    const ua = window.navigator.userAgent || "";
    const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(ua);
    if (!isMobile) return;

    // iOS Safari path — manual "Add to Home Screen" instructions
    const isIOS = /iPhone|iPad|iPod/i.test(ua);
    if (isIOS) {
      // Show banner immediately on iOS
      const t = setTimeout(() => setVisible(true), 4000);
      return () => clearTimeout(t);
    }

    // Android/Chromium path — wait for the deferred prompt
    const onInstallable = () => {
      setHasNativePrompt(true);
      setVisible(true);
    };
    window.addEventListener("eilatush:installable", onInstallable);

    // If the prompt was already captured before this component mounted
    if ((window as any).__eilatushDeferredPrompt) {
      setHasNativePrompt(true);
      setVisible(true);
    }

    return () => {
      window.removeEventListener("eilatush:installable", onInstallable);
    };
  }, []);

  const dismiss = (days = 14) => {
    setVisible(false);
    setShowIOSHelp(false);
    try {
      const until = Date.now() + days * 24 * 60 * 60 * 1000;
      localStorage.setItem(DISMISS_KEY, String(until));
    } catch (_) {}
  };

  const install = async () => {
    if (Platform.OS !== "web") return;
    const deferred = (window as any).__eilatushDeferredPrompt;
    if (deferred && typeof deferred.prompt === "function") {
      try {
        deferred.prompt();
        const { outcome } = await deferred.userChoice;
        (window as any).__eilatushDeferredPrompt = null;
        if (outcome === "accepted") {
          setVisible(false);
          try {
            localStorage.setItem("eilatush_pwa_installed", "1");
          } catch (_) {}
        } else {
          dismiss(3); // dismissed → ask again in 3 days
        }
      } catch (e) {
        console.warn("install prompt failed", e);
        dismiss(3);
      }
    } else {
      // No native prompt (iOS) → show manual instructions
      setShowIOSHelp(true);
    }
  };

  if (!visible) return null;

  // iOS manual instructions overlay
  if (showIOSHelp) {
    return (
      <View style={styles.iosOverlay}>
        <View style={styles.iosCard}>
          <Image source={MASCOT} style={styles.iosMascot} resizeMode="contain" />
          <Text style={styles.iosTitle}>הוסיפו את אילתוש למסך הבית</Text>
          <Text style={styles.iosStep}>
            1. הקישו על כפתור השיתוף{" "}
            <Text style={styles.iosIcon}>⬆️</Text> בתחתית המסך
          </Text>
          <Text style={styles.iosStep}>
            2. גללו ובחרו{" "}
            <Text style={{ fontWeight: "900" }}>"הוסף למסך הבית"</Text>{" "}
            <Text style={styles.iosIcon}>➕</Text>
          </Text>
          <Text style={styles.iosStep}>
            3. אשרו על-ידי{" "}
            <Text style={{ fontWeight: "900" }}>"הוסף"</Text>
          </Text>
          <Pressable
            onPress={() => dismiss(14)}
            style={styles.iosDismiss}
          >
            <Text style={styles.iosDismissText}>הבנתי</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.banner} accessibilityRole="alert">
      <Image source={MASCOT} style={styles.mascot} resizeMode="contain" />
      <View style={styles.textCol}>
        <Text style={styles.title}>הוסיפו את אילתוש למסך הבית</Text>
        <Text style={styles.subtitle}>בלי הורדה מהחנות — לחיצה אחת!</Text>
      </View>
      <View style={styles.actions}>
        <Pressable
          onPress={install}
          style={({ pressed }) => [
            styles.btnPrimary,
            pressed && styles.btnPrimaryPressed,
          ]}
          android_ripple={{ color: "rgba(255,255,255,0.20)" }}
        >
          <Text style={styles.btnPrimaryText}>
            {hasNativePrompt ? "התקנה" : "הוספה"}
          </Text>
        </Pressable>
        <Pressable
          onPress={() => dismiss(14)}
          hitSlop={10}
          style={styles.dismissBtn}
        >
          <Text style={styles.dismissText}>✕</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    position: "absolute",
    bottom: 88, // sit above the bottom tab bar
    left: SPACING.md,
    right: SPACING.md,
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.lg,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 10,
    borderWidth: 1,
    borderColor: "rgba(0,0,0,0.08)",
    ...Platform.select({
      web: {
        boxShadow: "0 8px 30px rgba(0,0,0,0.18)",
        animationName: "eilatushSlideUp",
        animationDuration: "0.4s",
        animationFillMode: "both",
      } as any,
      default: SHADOWS.md,
    }),
    zIndex: 9999,
  },
  mascot: {
    width: 44,
    height: 44,
  },
  textCol: {
    flex: 1,
    minWidth: 0,
  },
  title: {
    fontSize: 14,
    fontWeight: "900",
    color: COLORS.textPrimary,
    textAlign: "right",
    writingDirection: "rtl",
  },
  subtitle: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
    textAlign: "right",
    writingDirection: "rtl",
  },
  actions: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 6,
  },
  btnPrimary: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: RADIUS.md,
  },
  btnPrimaryPressed: {
    backgroundColor: COLORS.primaryHover,
  },
  btnPrimaryText: {
    color: COLORS.onPrimary,
    fontWeight: "900",
    fontSize: 14,
  },
  dismissBtn: {
    width: 28,
    height: 28,
    alignItems: "center",
    justifyContent: "center",
  },
  dismissText: {
    color: COLORS.textMuted,
    fontSize: 18,
    fontWeight: "700",
  },

  // ── iOS manual instructions ─────────────────────────────────────────────
  iosOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.55)",
    alignItems: "center",
    justifyContent: "center",
    padding: SPACING.md,
    zIndex: 99999,
  },
  iosCard: {
    width: "100%",
    maxWidth: 360,
    backgroundColor: COLORS.surface,
    borderRadius: RADIUS.xl,
    padding: SPACING.lg,
    alignItems: "center",
    ...Platform.select({
      web: { boxShadow: "0 14px 50px rgba(0,0,0,0.30)" } as any,
      default: SHADOWS.md,
    }),
  },
  iosMascot: {
    width: 76,
    height: 76,
    marginBottom: SPACING.sm,
  },
  iosTitle: {
    fontSize: 18,
    fontWeight: "900",
    color: COLORS.textPrimary,
    marginBottom: SPACING.md,
    textAlign: "center",
  },
  iosStep: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: "right",
    writingDirection: "rtl",
    marginBottom: 8,
    alignSelf: "stretch",
    lineHeight: 22,
  },
  iosIcon: {
    fontSize: 16,
  },
  iosDismiss: {
    marginTop: SPACING.md,
    backgroundColor: COLORS.primary,
    paddingHorizontal: SPACING.lg,
    paddingVertical: 12,
    borderRadius: RADIUS.md,
  },
  iosDismissText: {
    color: COLORS.onPrimary,
    fontWeight: "900",
    fontSize: 14,
  },
});
