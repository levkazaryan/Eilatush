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

// Card-with-"VIP" icon — prominent so it stands out from the other tabs
function CardVIPIcon({ focused, size = 30 }: { focused: boolean; size?: number }) {
  // Always rendered in primary coral so it stands out (other tabs are muted when inactive).
  // When focused: filled card with white "VIP". When inactive: filled card with white "VIP" too,
  // but slightly desaturated (lower opacity on the ring) so the active state is still recognisable.
  const cardColor = COLORS.primary; // always coral
  const cardW = size;
  const cardH = size * 0.66;
  return (
    <View
      style={{
        width: cardW,
        height: cardH,
        borderRadius: 6,
        backgroundColor: cardColor,
        alignItems: "center",
        justifyContent: "center",
        // Outer ring + lift to make it more visible than the others
        borderWidth: focused ? 2 : 0,
        borderColor: "#FFFFFF",
        ...Platform.select({
          ios: {
            shadowColor: cardColor,
            shadowOpacity: 0.45,
            shadowRadius: 8,
            shadowOffset: { width: 0, height: 3 },
          },
          android: { elevation: 6 },
          default: { boxShadow: "0 3px 10px rgba(230, 57, 70, 0.45)" } as any,
        }),
        transform: [{ scale: focused ? 1.08 : 1 }],
      }}
    >
      <Text
        style={{
          color: "#FFFFFF",
          fontSize: cardH * 0.55,
          fontWeight: "900",
          letterSpacing: 1,
          includeFontPadding: false as any,
          textAlignVertical: "center",
        }}
      >
        VIP
      </Text>
    </View>
  );
}

function VIPTabIcon({ focused }: { focused: boolean }) {
  const color = focused ? COLORS.primary : COLORS.textMuted;
  return (
    <View style={styles.tabItem} testID="tab-vip">
      <CardVIPIcon focused={focused} size={30} />
      <Text style={[styles.tabLabel, { color, marginTop: 4 }]} numberOfLines={1}>
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
});
