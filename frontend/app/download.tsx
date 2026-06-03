'use client';

import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Image,
  ScrollView,
  Platform,
  Modal,
  Linking,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { COLORS, RADIUS, SPACING, SHADOWS } from "../theme";

const MASCOT = require("../assets/images/eilatush-mascot.png");
const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=app.eilatush";
const WEB_APP_URL = "https://eilatush.app";

export default function DownloadPage() {
  const router = useRouter();
  const [showIOSHelp, setShowIOSHelp] = useState(false);

  useEffect(() => {
    if (Platform.OS !== "web" || typeof window === "undefined") return;
    // No-op — handled inline. Kept for future analytics if needed.
  }, []);

  // ─── Open Google Play ────────────────────────────────────────
  const openPlayStore = () => {
    if (Platform.OS === "web") {
      if (typeof window !== "undefined") {
        window.open(PLAY_STORE_URL, "_blank", "noopener,noreferrer");
      }
    } else {
      Linking.openURL(PLAY_STORE_URL).catch(() => {});
    }
  };

  // ─── Web install — trigger PWA prompt or redirect to eilatush.app ──────
  const handleWebInstall = async () => {
    if (Platform.OS !== "web") {
      // Native app: nothing to install — open eilatush.app in browser
      Linking.openURL(WEB_APP_URL).catch(() => {});
      return;
    }
    if (typeof window === "undefined") return;

    // If not on eilatush.app, redirect there first
    const currentHost = window.location.hostname;
    if (currentHost !== "eilatush.app" && !currentHost.includes("eilatush.app")) {
      window.location.href = `${WEB_APP_URL}/download?install=1`;
      return;
    }

    // Already on eilatush.app — try to trigger the install prompt
    const win = window;
    // @ts-expect-error custom global set by service worker integration in +html.tsx
    const deferred = win.__eilatushDeferredPrompt;
    if (deferred && typeof deferred.prompt === "function") {
      try {
        deferred.prompt();
        const { outcome } = await deferred.userChoice;
        win.__eilatushDeferredPrompt = null;
        if (outcome === "accepted") {
          try {
            localStorage.setItem("eilatush_pwa_installed", "1");
          } catch (_) {
            /* localStorage blocked → ignore */
          }
        }
      } catch (e) {
        console.warn("install prompt failed", e);
      }
    } else {
      // No native prompt → iOS or already installed or browser doesn't support it
      // Detect iOS
      const ua = window.navigator.userAgent.toLowerCase();
      const isIOS = /iphone|ipad|ipod/.test(ua) || (ua.includes("mac") && "ontouchend" in document);
      if (isIOS) {
        setShowIOSHelp(true);
      } else {
        // Desktop / other → show generic instructions
        setShowIOSHelp(true);
      }
    }
  };

  // ─── Auto-trigger install if ?install=1 in URL (after redirect) ────────
  useEffect(() => {
    if (Platform.OS !== "web" || typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("install") === "1") {
      // wait a tick for deferredPrompt to attach
      setTimeout(() => handleWebInstall(), 500);
    }
  }, []);

  return (
    <>
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.container}
        showsVerticalScrollIndicator={false}
      >
        {/* Back button */}
        <Pressable
          style={styles.backBtn}
          onPress={() => {
            if (router.canGoBack()) router.back();
            else router.replace("/");
          }}
          accessibilityLabel="חזרה"
        >
          <Ionicons name="chevron-forward" size={22} color={COLORS.textPrimary} />
        </Pressable>

        {/* Hero */}
        <View style={styles.hero}>
          <Image source={MASCOT} style={styles.mascot} resizeMode="contain" />
          <Text style={styles.appName}>אילתוש</Text>
          <Text style={styles.tagline}>הכל באילת במקום אחד</Text>
          <Text style={styles.subTagline}>הורידו עכשיו והישארו מעודכנים</Text>
        </View>

        {/* Buttons */}
        <View style={styles.buttonsWrap}>
          {/* Google Play */}
          <Pressable
            style={({ pressed }) => [styles.storeBtn, pressed && { opacity: 0.85 }]}
            onPress={openPlayStore}
            accessibilityRole="link"
            accessibilityLabel="הורד מ-Google Play"
          >
            <Ionicons name="logo-google-playstore" size={32} color="#fff" />
            <View style={styles.storeBtnText}>
              <Text style={styles.storeBtnSmall}>הורד באמצעות</Text>
              <Text style={styles.storeBtnBig}>Google Play</Text>
            </View>
          </Pressable>

          {/* App Store — coming soon */}
          <View style={[styles.storeBtn, styles.storeBtnDisabled]}>
            <Ionicons name="logo-apple" size={32} color="#fff" />
            <View style={styles.storeBtnText}>
              <Text style={styles.storeBtnSmall}>בקרוב ב</Text>
              <Text style={styles.storeBtnBig}>App Store</Text>
            </View>
            <View style={styles.comingSoonBadge}>
              <Text style={styles.comingSoonBadgeText}>בקרוב</Text>
            </View>
          </View>

          {/* Web — install PWA */}
          <Pressable
            style={({ pressed }) => [styles.storeBtn, styles.storeBtnWeb, pressed && { opacity: 0.85 }]}
            onPress={handleWebInstall}
            accessibilityRole="button"
            accessibilityLabel="התקן את אפליקציית האינטרנט"
          >
            <Ionicons name="globe-outline" size={32} color="#fff" />
            <View style={styles.storeBtnText}>
              <Text style={styles.storeBtnSmall}>גרסת אינטרנט</Text>
              <Text style={styles.storeBtnBig}>פתח באתר</Text>
            </View>
          </Pressable>
        </View>

        {/* Footer note */}
        <Text style={styles.footerNote}>
          האפליקציה חינמית • ללא פרסומות • נתונים ממקורות רשמיים
        </Text>
      </ScrollView>

      {/* PWA install helper modal */}
      <Modal
        visible={showIOSHelp}
        animationType="fade"
        transparent
        onRequestClose={() => setShowIOSHelp(false)}
      >
        <Pressable
          style={styles.modalBackdrop}
          onPress={() => setShowIOSHelp(false)}
        >
          <Pressable
            style={styles.modalCard}
            onPress={(e) => e.stopPropagation()}
          >
            <Image source={MASCOT} style={styles.modalMascot} resizeMode="contain" />
            <Text style={styles.modalTitle}>הוסיפו את אילתוש למסך הבית</Text>
            <Text style={styles.modalStep}>
              1. הקישו על כפתור השיתוף{" "}
              <Text style={styles.modalIcon}>⬆️</Text> בדפדפן
            </Text>
            <Text style={styles.modalStep}>
              2. בחרו <Text style={styles.modalBold}>&quot;הוסף למסך הבית&quot;</Text>
            </Text>
            <Text style={styles.modalStep}>
              3. הקישו <Text style={styles.modalBold}>&quot;הוסף&quot;</Text> בפינה
            </Text>
            <Pressable style={styles.modalCloseBtn} onPress={() => setShowIOSHelp(false)}>
              <Text style={styles.modalCloseText}>הבנתי 👍</Text>
            </Pressable>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  scroll: {
    flex: 1,
    backgroundColor: COLORS.bg,
  },
  container: {
    padding: SPACING.lg,
    paddingTop: SPACING.xl,
    paddingBottom: SPACING.xxl * 2,
    alignItems: "center",
  },
  backBtn: {
    position: "absolute",
    top: SPACING.md,
    left: SPACING.md,
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: COLORS.surface,
    alignItems: "center",
    justifyContent: "center",
    ...SHADOWS.sm,
    zIndex: 10,
  },
  // Hero
  hero: {
    alignItems: "center",
    marginTop: SPACING.lg,
    marginBottom: SPACING.xl,
  },
  mascot: {
    width: 140,
    height: 140,
    marginBottom: SPACING.md,
  },
  appName: {
    fontSize: 36,
    fontWeight: "900",
    color: COLORS.primary,
    letterSpacing: -1,
    marginBottom: SPACING.xs,
  },
  tagline: {
    fontSize: 18,
    fontWeight: "700",
    color: COLORS.textPrimary,
    marginBottom: SPACING.xs,
  },
  subTagline: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: "center",
  },
  // Buttons
  buttonsWrap: {
    width: "100%",
    maxWidth: 380,
    gap: SPACING.md,
    marginBottom: SPACING.xl,
  },
  storeBtn: {
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: "#0F172A",
    borderRadius: RADIUS.lg,
    padding: SPACING.md,
    paddingHorizontal: SPACING.lg,
    gap: SPACING.md,
    minHeight: 72,
    ...SHADOWS.md,
    position: "relative",
  },
  storeBtnWeb: {
    backgroundColor: "#0172E5",
  },
  storeBtnDisabled: {
    backgroundColor: "#94A3B8",
    opacity: 0.85,
  },
  storeBtnText: {
    flex: 1,
    alignItems: "flex-end",
  },
  storeBtnSmall: {
    color: "rgba(255,255,255,0.85)",
    fontSize: 11,
    fontWeight: "500",
    marginBottom: 2,
  },
  storeBtnBig: {
    color: "#fff",
    fontSize: 19,
    fontWeight: "800",
  },
  comingSoonBadge: {
    position: "absolute",
    top: 8,
    left: 8,
    backgroundColor: "#F59E0B",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: RADIUS.sm,
  },
  comingSoonBadgeText: {
    color: "#fff",
    fontSize: 10,
    fontWeight: "800",
  },
  footerNote: {
    fontSize: 12,
    color: COLORS.textMuted,
    textAlign: "center",
    maxWidth: 320,
    lineHeight: 18,
  },
  // Modal
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.55)",
    alignItems: "center",
    justifyContent: "center",
    padding: SPACING.lg,
  },
  modalCard: {
    backgroundColor: "#fff",
    borderRadius: RADIUS.xl,
    padding: SPACING.lg,
    width: "100%",
    maxWidth: 360,
    alignItems: "center",
    ...SHADOWS.lg,
  },
  modalMascot: {
    width: 80,
    height: 80,
    marginBottom: SPACING.md,
  },
  modalTitle: {
    fontSize: 19,
    fontWeight: "800",
    color: COLORS.textPrimary,
    textAlign: "center",
    marginBottom: SPACING.md,
  },
  modalStep: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: "right",
    width: "100%",
    marginBottom: SPACING.sm,
    lineHeight: 22,
  },
  modalBold: {
    fontWeight: "800",
    color: COLORS.textPrimary,
  },
  modalIcon: {
    fontSize: 18,
  },
  modalCloseBtn: {
    marginTop: SPACING.md,
    backgroundColor: COLORS.primary,
    paddingVertical: SPACING.sm,
    paddingHorizontal: SPACING.xl,
    borderRadius: RADIUS.lg,
  },
  modalCloseText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "800",
  },
});
