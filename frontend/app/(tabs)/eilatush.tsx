'use client';

import React, { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Image,
  Pressable,
  Share,
  Linking,
  Alert,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { api } from "../../api";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { EventCard, BusinessCard, JobCard, NewsCard } from "../../components";

const MASCOT_IMG = require("../../assets/images/eilatush-mascot.png");

type ResultItem =
  | { type: "event"; item: any }
  | { type: "business"; item: any }
  | { type: "job"; item: any }
  | { type: "news"; item: any };

type Msg = {
  id: string;
  role: "user" | "bot";
  text: string;
  results?: ResultItem[];
  intent?: string;
  followUps?: string[];
};

const DEFAULT_FOLLOWUPS = [
  "מה קורה הערב?",
  "ברים פתוחים עכשיו",
  "עבודה דחופה",
  "סושי זול",
  "חדשות מהעירייה",
  "מסיבות הלילה",
];

const STORAGE_KEY = "eilatush_chat_v2";
const SESSION_KEY = "eilatush_session_v2";
const MAX_HISTORY = 40; // keep last N messages in storage

const CONTACT_PHONE = "972535319943"; // +972-53-531-9943
const APP_URL =
  (typeof process !== "undefined" && process.env?.EXPO_PUBLIC_APP_URL) ||
  "https://eilat-connect.preview.emergentagent.com";
const SHARE_MSG = `היי 👋
גיליתי את אילתוש 🐠 - אפליקציה שמרכזת הכל על אילת:
אירועים, עסקים, עבודה, חדשות ואיש קשר חכם שיודע הכל על העיר.
שווה לבדוק:
${APP_URL}`;

async function openWhatsApp() {
  const text = encodeURIComponent(
    "היי, הגעתי מהאפליקציה אילתוש. אשמח לעזרה / פידבק 🙂",
  );
  const appUrl = `whatsapp://send?phone=${CONTACT_PHONE}&text=${text}`;
  const webUrl = `https://wa.me/${CONTACT_PHONE}?text=${text}`;
  try {
    if (Platform.OS === "web") {
      // On web, canOpenURL always returns true for any scheme, so skip it
      // and go straight to the public wa.me URL which works in every browser.
      await Linking.openURL(webUrl);
      return;
    }
    const canApp = await Linking.canOpenURL(appUrl);
    await Linking.openURL(canApp ? appUrl : webUrl);
  } catch (e) {
    try {
      await Linking.openURL(webUrl);
    } catch (err) {
      Alert.alert("שגיאה", "לא הצלחנו לפתוח את WhatsApp. נסו שוב.");
    }
  }
}

async function inviteFriend() {
  try {
    if (Platform.OS === "web") {
      // Web share API if available, fallback to clipboard copy
      const nav: any = (globalThis as any).navigator;
      if (nav?.share) {
        await nav.share({ title: "אילתוש 🐠", text: SHARE_MSG, url: APP_URL });
        return;
      }
      if (nav?.clipboard?.writeText) {
        await nav.clipboard.writeText(SHARE_MSG);
        Alert.alert("הקישור הועתק ✨", "הדביקו אותו איפה שתרצו ושלחו לחבר");
        return;
      }
    }
    await Share.share({ message: SHARE_MSG, url: APP_URL, title: "אילתוש 🐠" });
  } catch (e) {
    // user cancelled or platform refused — silent.
  }
}

export default function EilatushScreen() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: "welcome",
      role: "bot",
      text: "היי! אני אילתוש 🌴\nאני כאן כדי לעזור לך לגלות מה קורה בעיר - אירועים, מקומות לאכול, עבודה, חדשות. שאל/י אותי כל דבר ואני אחזור עם הכל בתוך שניות.",
      followUps: DEFAULT_FOLLOWUPS.slice(0, 3),
    },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  // ---- persistence ----
  useEffect(() => {
    (async () => {
      try {
        const [rawMsgs, rawSess] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEY),
          AsyncStorage.getItem(SESSION_KEY),
        ]);
        if (rawMsgs) {
          const saved = JSON.parse(rawMsgs);
          if (Array.isArray(saved) && saved.length > 0) {
            setMessages(saved);
          }
        }
        if (rawSess) setSessionId(rawSess);
      } catch (e) {
        console.warn("chat load failed", e);
      } finally {
        setHydrated(true);
      }
    })();
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    const trimmed = messages.slice(-MAX_HISTORY);
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed)).catch(() => {});
  }, [messages, hydrated]);

  useEffect(() => {
    if (!hydrated || !sessionId) return;
    AsyncStorage.setItem(SESSION_KEY, sessionId).catch(() => {});
  }, [sessionId, hydrated]);

  const clearChat = async () => {
    const doClear = () => {
      setMessages([
        {
          id: "welcome",
          role: "bot",
          text: "שיחה חדשה! על מה נתחיל?",
          followUps: DEFAULT_FOLLOWUPS.slice(0, 3),
        },
      ]);
      setSessionId(undefined);
      Promise.all([
        AsyncStorage.removeItem(STORAGE_KEY),
        AsyncStorage.removeItem(SESSION_KEY),
      ]).catch(() => {});
    };
    if (Platform.OS === "web") {
      doClear();
      return;
    }
    Alert.alert("שיחה חדשה", "לנקות את ההיסטוריה ולהתחיל שיחה חדשה?", [
      { text: "ביטול", style: "cancel" },
      { text: "נקה", style: "destructive", onPress: doClear },
    ]);
  };

  const send = async (msg?: string) => {
    const text = (msg ?? input).trim();
    if (!text || loading) return;
    setInput("");
    const userMsg: Msg = { id: `u-${Date.now()}`, role: "user", text };
    // Build history from visible (non-welcome) messages
    const history = messages
      .filter((m) => m.id !== "welcome")
      .slice(-8)
      .map((m) => ({ role: m.role === "user" ? "user" : "assistant", text: m.text }));
    setMessages((m) => [...m, userMsg]);
    setLoading(true);
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
    try {
      const res = await api.chat(text, sessionId, history);
      if (res.session_id) setSessionId(res.session_id);
      const botMsg: Msg = {
        id: `b-${Date.now()}`,
        role: "bot",
        text: res.reply || "הנה מה שמצאתי",
        results: res.results || [],
        intent: res.intent,
        followUps: Array.isArray(res.follow_ups) && res.follow_ups.length
          ? res.follow_ups
          : undefined,
      };
      setMessages((m) => [...m, botMsg]);
    } catch (e) {
      console.warn("chat err", e);
      setMessages((m) => [
        ...m,
        { id: `b-${Date.now()}`, role: "bot", text: "מצטער, משהו השתבש. נסו שוב." },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
    }
  };

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 90 : 0}
      >
        <View style={styles.header}>
          <View style={styles.brandRow}>
            <View style={styles.mascot}>
              <Image source={MASCOT_IMG} style={styles.mascotImg} resizeMode="contain" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.headerTitle}>אילתוש</Text>
              <Text style={styles.headerSub}>העוזר המקומי שלך · תמיד כאן</Text>
            </View>
            <View style={styles.headerActions}>
              <Pressable
                onPress={clearChat}
                style={({ pressed }) => [
                  styles.headerIconBtn,
                  pressed && { opacity: 0.6 },
                ]}
                accessibilityLabel="שיחה חדשה"
                testID="header-clear"
              >
                <Ionicons name="refresh" size={20} color={COLORS.primary} />
              </Pressable>
              <Pressable
                onPress={inviteFriend}
                style={({ pressed }) => [
                  styles.headerIconBtn,
                  pressed && { opacity: 0.6 },
                ]}
                accessibilityLabel="הזמן חבר"
                testID="header-invite"
              >
                <Ionicons name="share-social-outline" size={20} color={COLORS.primary} />
              </Pressable>
              <Pressable
                onPress={openWhatsApp}
                style={({ pressed }) => [
                  styles.headerIconBtn,
                  { backgroundColor: "#25D366" },
                  pressed && { opacity: 0.7 },
                ]}
                accessibilityLabel="צור קשר בוואטסאפ"
                testID="header-contact"
              >
                <Ionicons name="logo-whatsapp" size={20} color="#fff" />
              </Pressable>
            </View>
          </View>
        </View>

        <ScrollView
          ref={scrollRef}
          contentContainerStyle={{ padding: SPACING.md, paddingBottom: 20 }}
        >
          {messages.map((m) => (
            <View key={m.id} style={{ marginBottom: SPACING.md }}>
              {m.role === "user" ? (
                <View style={styles.userBubbleWrap}>
                  <View style={styles.userBubble}>
                    <Text style={styles.userText}>{m.text}</Text>
                  </View>
                </View>
              ) : (
                <View style={styles.botWrap}>
                  <View style={styles.mascotSmall}>
                    <Image source={MASCOT_IMG} style={styles.mascotSmallImg} resizeMode="contain" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <View style={styles.botBubble}>
                      <Text style={styles.botText}>{m.text}</Text>
                    </View>
                    {m.results && m.results.length > 0 && (
                      <View style={{ marginTop: 10, marginHorizontal: -SPACING.md }}>
                        {m.results.map((r, idx) => (
                          <View key={`${m.id}-${idx}`}>
                            {r.type === "event" && <EventCard item={r.item} />}
                            {r.type === "business" && <BusinessCard item={r.item} />}
                            {r.type === "job" && <JobCard item={r.item} />}
                            {r.type === "news" && <NewsCard item={r.item} />}
                          </View>
                        ))}
                      </View>
                    )}
                    {m.followUps && m.followUps.length > 0 && !loading && (
                      <View style={styles.sugWrap}>
                        {m.followUps.slice(0, 6).map((s) => (
                          <Pressable
                            key={`${m.id}-fu-${s}`}
                            onPress={() => send(s)}
                            style={({ pressed }) => [styles.sugChip, pressed && { opacity: 0.7 }]}
                            testID={`followup-${s}`}
                          >
                            <Ionicons
                              name="sparkles-outline"
                              size={12}
                              color={COLORS.secondary}
                              style={{ marginStart: 4 }}
                            />
                            <Text style={styles.sugChipText}>{s}</Text>
                          </Pressable>
                        ))}
                      </View>
                    )}
                  </View>
                </View>
              )}
            </View>
          ))}
          {loading && (
            <View style={styles.botWrap}>
              <View style={styles.mascotSmall}>
                <Image source={MASCOT_IMG} style={styles.mascotSmallImg} resizeMode="contain" />
              </View>
              <View style={styles.botBubble}>
                <ActivityIndicator color={COLORS.primary} size="small" />
              </View>
            </View>
          )}
        </ScrollView>

        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="שאל את אילתוש..."
            placeholderTextColor={COLORS.textMuted}
            onSubmitEditing={() => send()}
            returnKeyType="send"
            testID="eilatush-input"
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || loading) && { opacity: 0.5 }]}
            onPress={() => send()}
            disabled={!input.trim() || loading}
            testID="eilatush-send"
          >
            <Ionicons name="arrow-up" size={20} color="#fff" />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.md,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  brandRow: { flexDirection: "row-reverse", alignItems: "center", gap: 12 },
  mascot: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#FFE8D6",
    alignItems: "center",
    justifyContent: "center",
    overflow: "hidden",
  },
  mascotImg: {
    width: 42,
    height: 42,
  },
  mascotSmall: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#FFE8D6",
    alignItems: "center",
    justifyContent: "center",
    marginStart: 8,
    overflow: "hidden",
  },
  mascotSmallImg: {
    width: 28,
    height: 28,
  },
  headerTitle: { color: COLORS.textPrimary, fontSize: 20, fontWeight: "900", textAlign: "right" },
  headerSub: { color: COLORS.textMuted, fontSize: 12, textAlign: "right" },

  userBubbleWrap: { alignItems: "flex-start" },
  userBubble: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: RADIUS.lg,
    borderBottomStartRadius: 4,
    maxWidth: "85%",
  },
  userText: { color: "#fff", fontSize: 14, writingDirection: "rtl", textAlign: "right" },

  botWrap: { flexDirection: "row-reverse", alignItems: "flex-start" },
  botBubble: {
    backgroundColor: COLORS.card,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: RADIUS.lg,
    borderBottomEndRadius: 4,
    borderWidth: 1,
    borderColor: COLORS.border,
    maxWidth: "85%",
    alignSelf: "flex-end",
  },
  botText: { color: COLORS.textPrimary, fontSize: 14, writingDirection: "rtl", textAlign: "right", lineHeight: 20 },

  sugWrap: {
    flexDirection: "row-reverse",
    flexWrap: "wrap",
    marginTop: 10,
    gap: 8,
  },
  sugChip: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(20,184,179,0.10)",
    borderColor: "rgba(20,184,179,0.35)",
    borderWidth: 1,
  },
  sugChipText: { color: COLORS.secondary, fontSize: 13, fontWeight: "700" },

  headerActions: {
    flexDirection: "row-reverse",
    alignItems: "center",
    gap: 8,
  },
  headerIconBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(20,184,179,0.10)",
    borderWidth: 1,
    borderColor: "rgba(20,184,179,0.30)",
  },

  ctaRow: {
    flexDirection: "row-reverse",
    gap: 10,
    marginTop: 12,
  },
  ctaChip: {
    flex: 1,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 11,
    paddingHorizontal: 14,
    borderRadius: RADIUS.pill,
    minHeight: 44,
  },
  ctaInvite: {
    backgroundColor: "rgba(20,184,179,0.12)",
    borderWidth: 1,
    borderColor: "rgba(20,184,179,0.40)",
  },
  ctaContact: {
    backgroundColor: "#25D366",
  },
  ctaText: { fontSize: 14, fontWeight: "800" },

  inputRow: {
    flexDirection: "row-reverse",
    alignItems: "center",
    padding: SPACING.md,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    backgroundColor: COLORS.bg,
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: COLORS.card,
    color: COLORS.textPrimary,
    borderRadius: RADIUS.pill,
    paddingHorizontal: 18,
    height: 46,
    fontSize: 14,
    borderWidth: 1,
    borderColor: COLORS.border,
    textAlign: "right",
    writingDirection: "rtl",
    ...({ outlineStyle: "none" } as any),
  },
  sendBtn: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: COLORS.primary,
    alignItems: "center",
    justifyContent: "center",
  },
});
