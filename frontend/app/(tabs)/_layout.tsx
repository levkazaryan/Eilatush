import React from "react";
import { Tabs } from "expo-router";
import { View, Text, StyleSheet, Platform, Image } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { COLORS } from "../../theme";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

const EILATUSH_MASCOT = require("../../assets/images/eilatush-mascot.png");

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
        name="eilatush"
        options={{
          title: "אילתוש",
          tabBarIcon: ({ focused }) => (
            <View style={styles.centerItem} testID="tab-eilatush">
              <View style={[styles.centerMascotWrap, focused && styles.centerMascotWrapActive]}>
                <Image
                  source={EILATUSH_MASCOT}
                  style={styles.centerMascotImg}
                  resizeMode="contain"
                />
              </View>
              <Text
                numberOfLines={1}
                style={[styles.tabLabel, styles.centerLabel, { color: focused ? COLORS.primary : COLORS.textMuted }]}
              >
                אילתוש
              </Text>
            </View>
          ),
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
  centerItem: {
    alignItems: "center",
    justifyContent: "center",
    marginTop: -16,
    minWidth: 80,   // ensure label never wraps regardless of parent width
  },
  centerLabel: {
    marginTop: 2,
    paddingHorizontal: 4,
    includeFontPadding: false as any,
  },
  centerBubble: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: COLORS.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: COLORS.primary,
    shadowOpacity: 0.45,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
    borderWidth: 3,
    borderColor: "#FFFFFF",
  },
  centerBubbleActive: {
    backgroundColor: COLORS.primaryHover,
  },
  centerMascotWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#FFFFFF",
    shadowColor: "#000",
    shadowOpacity: 0.18,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 3 },
    elevation: 6,
  },
  centerMascotWrapActive: {
    shadowColor: COLORS.primary,
    shadowOpacity: 0.45,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 4 },
    elevation: 10,
    transform: [{ scale: 1.05 }],
  },
  centerMascotImg: {
    width: 54,
    height: 54,
  },
});
