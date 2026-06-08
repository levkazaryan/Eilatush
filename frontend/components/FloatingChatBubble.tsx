'use client';

import React from "react";
import { View, Text, StyleSheet, Pressable, Image, Platform } from "react-native";
import { router, usePathname } from "expo-router";

const MASCOT = require("../assets/images/eilatush-mascot.png");

/**
 * FloatingChatBubble — sits above the bottom tab bar in the bottom-right corner.
 * Tap navigates to the standalone /chat screen.
 * Auto-hides when already on the /chat route to avoid visual stacking.
 */
export default function FloatingChatBubble() {
  const path = usePathname();
  // Hide when chat is already open
  if (path === "/chat") return null;

  return (
    <View pointerEvents="box-none" style={styles.host}>
      <Pressable
        onPress={() => router.push("/chat")}
        accessibilityLabel="פתח את אילתוש"
        testID="floating-chat-bubble"
        style={({ pressed }) => [
          styles.bubble,
          pressed && { transform: [{ scale: 0.94 }] },
        ]}
      >
        <Image source={MASCOT} style={styles.mascot} resizeMode="contain" />
        <View style={styles.dot} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  host: {
    position: "absolute",
    // Position above the tab bar. Tab bar is ~78 native / 68 web, leave room.
    bottom: Platform.OS === "web" ? 82 : 96,
    right: 14,
    zIndex: 999,
  },
  bubble: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 2,
    borderColor: "#14B8B3",
    ...Platform.select({
      ios: {
        shadowColor: "#0F172A",
        shadowOpacity: 0.25,
        shadowRadius: 14,
        shadowOffset: { width: 0, height: 6 },
      },
      android: { elevation: 10 },
      default: { boxShadow: "0 6px 18px rgba(0,0,0,0.25)" } as any,
    }),
  },
  mascot: {
    width: 56,
    height: 56,
  },
  dot: {
    position: "absolute",
    top: 4,
    right: 4,
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: "#22C55E",
    borderWidth: 1.5,
    borderColor: "#FFFFFF",
  },
});
