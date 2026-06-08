'use client';

import React from "react";
import { Tabs } from "expo-router";
import { View, Text, StyleSheet, Platform } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import Svg, { Path, Rect, G } from "react-native-svg";
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

// Monochrome "card with dolphin" icon — matches the flat design of the other tabs
function CardDolphinIcon({ color, size = 24 }: { color: string; size?: number }) {
  // viewBox 24x24; card is a rounded rect, dolphin silhouette overlaid centered
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      {/* Card outline */}
      <Rect
        x={2}
        y={5}
        width={20}
        height={14}
        rx={2.5}
        ry={2.5}
        stroke={color}
        strokeWidth={1.8}
        fill="none"
      />
      {/* Small dolphin silhouette centered on card */}
      <G transform="translate(6.5 7.2) scale(0.022)">
        <Path
          d="M123.22 47.23c29.498 15.152 55.025 36.05 55.53 67.366c-93.62 83.867-83.862 179.356-97.002 270.34c-67.68 55.552-67.57 90.948-60.9 101.227c3.94.743 29.11-25.94 48.326-30.397c14.23-4.094 12.284-15.99 16.273-25.275c2.438 14.55 7.17 22.612 17.133 25.485c12.874 3.36 44.932 28.15 51.53 25.504c1.374-20.382-26.01-63.854-48.028-90.087c41.012-63.28 81.365-136.458 211.162-207.77c-3.21-3.706-6.216-6.45-8.8-7.986l9.198-15.472c11.617 6.907 20.522 19.56 29.248 35.033c5.94 10.532 11.528 22.644 16.96 35.117c15.682-32.87 22.983-66.406 16.402-90.254l17.35-4.786a87 87 0 0 1 1.927 8.83c33.29-4.253 55.718-13.083 85.11-29.322c3.744-2.068 19.054-13.012-.117-16.03c12.62-9.017 7.54-12.063 1.973-15.152c-6.486-3.6-20.302-8.948-35.758-8.556c-12.124-27.863-39.63-47.772-82.225-47.696c-28.532.052-63.842 9.086-105.828 30.688C217.895 27.64 164.92 20.468 123.22 47.23"
          fill={color}
        />
      </G>
    </Svg>
  );
}

function VIPTabIcon({ focused }: { focused: boolean }) {
  const color = focused ? COLORS.primary : COLORS.textMuted;
  return (
    <View style={styles.tabItem} testID="tab-vip">
      <CardDolphinIcon color={color} size={24} />
      <Text style={[styles.tabLabel, { color }]} numberOfLines={1}>
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
