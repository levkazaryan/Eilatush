import { useEffect } from "react";
import { Stack } from "expo-router";
import { I18nManager, Platform } from "react-native";
import { StatusBar } from "expo-status-bar";

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
  useEffect(() => {
    if (Platform.OS === "web" && typeof document !== "undefined") {
      document.documentElement.setAttribute("dir", "rtl");
      document.documentElement.setAttribute("lang", "he");
      document.body.style.backgroundColor = "#0C0C12";
    }
  }, []);

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: "#0C0C12" },
        }}
      />
    </>
  );
}
