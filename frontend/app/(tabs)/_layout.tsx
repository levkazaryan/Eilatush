'use client';

import React from "react";
import { Tabs } from "expo-router";
import { View, Text, StyleSheet, Platform } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "../../theme";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

function TabIcon({ focused, name, label, testID }: { focused: boolean; name: IconName; label: string; testID: string }) {
  return (
    <View style={styles.tabItem} testID={testID}>
      <Ionicons name={name} size={22} color={focused ? COLORS.primary : COLORS.textMuted} />
      <Text style={[styles.tabLabel, { color: focused ? COLORS.primary : COLORS.textMuted }]} numberOfLines={1}>
        {label}
      </Text>
    </View>
  );
}

function VIPTabIcon({ focused }: { focused: boolean }) {
  return (
    <View style={styles.centerItem} testID="tab-vip">
      <View style={[styles.vipBubble, focused && styles.vipBubbleActive]}>
        <Ionicons name="diamond" size={26} color={focused ? "#000" : "#000"} />
      </View>
      <Text
        numberOfLines={1}
        style={[styles.tabLabel, styles.centerLabel, { color: focused ? "#A57C1B" : COLORS.textMuted }]}
      >
        VIP
      </Text>
    </View>
  );
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarShowLabel: false,
        tabBarStyle: {
          backgroundColor: "#FFFFFF",
          borderTopColor: COLORS.border,
          borderTopWidth: 1,
          height: Platform.OS === "web" ? 68 : 78,
          paddingTop: 8,
          paddingBottom: Platform.OS === "web" ? 8 : 18,
        },
        tabBarActiveTintColor: COLORS.primary,
        tabBarInactiveTintColor: COLORS.textMuted,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "בית",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name={focused ? "flame" : "flame-outline"} label="עכשיו" testID="tab-home" />
          ),
        }}
      />
      <Tabs.Screen
        name="businesses"
        options={{
          title: "עסקים",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name={focused ? "storefront" : "storefront-outline"} label="עסקים" testID="tab-businesses" />
          ),
        }}
      />
      <Tabs.Screen
        name="vip"
        options={{
          title: "VIP",
          tabBarIcon: ({ focused }) => <VIPTabIcon focused={focused} />,
        }}
      />
      <Tabs.Screen
        name="jobs"
        options={{
          title: "עבודה",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name={focused ? "briefcase" : "briefcase-outline"} label="עבודה" testID="tab-jobs" />
          ),
        }}
      />
      <Tabs.Screen
        name="news"
        options={{
          title: "חדשות",
          tabBarIcon: ({ focused }) => (
            <TabIcon focused={focused} name={focused ? "newspaper" : "newspaper-outline"} label="חדשות" testID="tab-news" />
          ),
        }}
      />
    </Tabs>
  );
}

const GOLD = "#D4AF37";
const GOLD_LIGHT = "#F2D785";

const styles = StyleSheet.create({
  tabItem: {
    alignItems: "center",
    justifyContent: "center",
    minWidth: 56,
  },
  tabLabel: {
    fontSize: 11,
    marginTop: 2,
    fontWeight: "600",
    textAlign: "center",
  },
  centerItem: {
    alignItems: "center",
    justifyContent: "center",
    marginTop: -22,
    minWidth: 80,
  },
  centerLabel: {
    marginTop: 2,
    paddingHorizontal: 4,
    includeFontPadding: false as any,
    fontWeight: "900",
    letterSpacing: 1.2,
  },
  vipBubble: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: GOLD,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 3,
    borderColor: "#FFFFFF",
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOpacity: 0.35,
        shadowRadius: 12,
        shadowOffset: { width: 0, height: 4 },
      },
      android: { elevation: 8 },
      default: { boxShadow: "0 4px 14px rgba(212,175,55,0.55)" } as any,
    }),
  },
  vipBubbleActive: {
    backgroundColor: GOLD_LIGHT,
  },
});
