'use client';

import { useEffect, useState } from "react";
import { Stack } from "expo-router";
import { I18nManager, LogBox, Platform } from "react-native";
import { StatusBar } from "expo-status-bar";
import { COLORS } from "../theme";
import { trackAppOpen } from "../utils/analytics";
import { checkForUpdate, type UpdateDecision } from "../utils/version-check";
import UpdateModal from "../components/UpdateModal";

// Silence noisy dev-only warnings that overlay the UI in Expo Go
LogBox.ignoreLogs([
  "Cannot read properties of undefined (reading 'body')",
  "expo-keep-awake",
  "ExpoKeepAwake",
  "new NativeEventEmitter",
  "Require cycle:",
]);

// Force RTL on native; on web we toggle document.dir
if (Platform.OS !== "web") {
  try {
    I18nManager.allowRTL(true);
    if (!I18nManager.isRTL) {
      I18nManager.forceRTL(true);
    }
  } catch (e) {
    console.warn("RTL force failed", e);
  }
}

export default function RootLayout() {
  const [updateDecision, setUpdateDecision] = useState<UpdateDecision>({ kind: "none" });

  useEffect(() => {
    if (Platform.OS === "web" && typeof document !== "undefined") {
      document.documentElement.setAttribute("dir", "rtl");
      document.documentElement.setAttribute("lang", "he");
      document.body.style.backgroundColor = COLORS.bg;
    }
    // Track app open (analytics)
    trackAppOpen();

    // Check for app update — non-blocking, runs in background.
    // If a newer version is available we surface a friendly modal.
    let cancelled = false;
    (async () => {
      try {
        const decision = await checkForUpdate();
        if (!cancelled) setUpdateDecision(decision);
      } catch (e) {
        // Silent — never block the app for update-check failures
        console.warn("update check failed", e);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: COLORS.bg },
        }}
      />
      <UpdateModal
        decision={updateDecision}
        onDismiss={() => setUpdateDecision({ kind: "none" })}
      />
    </>
  );
}
