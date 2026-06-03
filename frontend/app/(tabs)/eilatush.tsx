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
import { router } from "expo-router";
import { api } from "../../api";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { EventCard, BusinessCard, JobCard, NewsCard } from "../../components";
import { trackScreen } from "../../utils/analytics";

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

const STORAGE_KEY = "eilatush_chat_v3";
const SESSION_KEY = "eilatush_session_v3";
const GENDER_KEY = "eilatush_user_gender_v1";
const MAX_HISTORY = 40; // keep last N messages in storage

type UserGender = "m" | "f" | null;

const GENDER_SELECT_ID = "gender-select";

function welcomeTextFor(g: UserGender): string {
  if (g === "m") {
    return "היי! אני אילתוש 🌴\nאני כאן כדי לעזור לך לגלות מה קורה בעיר - אירועים, מקומות לאכול, עבודה, חדשות. שאל אותי כל דבר ואני אחזור עם הכל בתוך שניות.";
  }
  if (g === "f") {
    return "היי! אני אילתוש 🌴\nאני כאן כדי לעזור לך לגלות מה קורה בעיר - אירועים, מקומות לאכול, עבודה, חדשות. שאלי אותי כל דבר ואני אחזור עם הכל בתוך שניות.";
  }
  return "";
}

function buildWelcomeMsg(g: UserGender, freshChat = false): Msg {
  if (!g) {
    return {
      id: GENDER_SELECT_ID,
      role: "bot",
      text: "היי! אני אילתוש 🌴\nשמחה להכיר! לפני שנתחיל - איך מתאים לך שאפנה?",
    };
  }
  return {
    id: "welcome",
    role: "bot",
    text: freshChat ? "שיחה חדשה! על מה נתחיל?" : welcomeTextFor(g),
    followUps: DEFAULT_FOLLOWUPS.slice(0, 3),
  };
}

const CONTACT_PHONE = "972535319943"; // +972-53-531-9943
const APP_URL =
  (typeof process !== "undefined" && process.env?.EXPO_PUBLIC_APP_URL) ||
  "https://eilat-connect.preview.emergentagent.com";
const SHARE_MSG = `היי 👋
גיליתי את אילתוש 🌴 - אפליקציה שמרכזת הכל על אילת:
אירועים, עסקים, עבודה, חדשות ועוזרת חכמה שיודעת הכל על העיר.
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
  const [userGender, setUserGender] = useState<UserGender>(null);
  const [messages, setMessages] = useState<Msg[]>([buildWelcomeMsg(null)]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  // ---- persistence ----
  useEffect(() => {
    trackScreen("eilatush");
    (async () => {
      try {
        const [rawMsgs, rawSess, rawGender] = await Promise.all([
          AsyncStorage.getItem(STORAGE_KEY),
          AsyncStorage.getItem(SESSION_KEY),
          AsyncStorage.getItem(GENDER_KEY),
        ]);
        const g: UserGender =
          rawGender === "m" || rawGender === "f" ? rawGender : null;
        setUserGender(g);
        if (rawSess) setSessionId(rawSess);

        let hydratedFromSaved = false;
        if (rawMsgs) {
          try {
            const saved = JSON.parse(rawMsgs);
            if (Array.isArray(saved) && saved.length > 0) {
              setMessages(saved);
              hydratedFromSaved = true;
            }
          } catch {}
        }
        if (!hydratedFromSaved) {
          setMessages([buildWelcomeMsg(g)]);
        }
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

  const pickGender = async (g: UserGender) => {
    if (!g) return;
    setUserGender(g);
    AsyncStorage.setItem(GENDER_KEY, g).catch(() => {});
    // Replace the gender-select message with a tailored welcome
    setMessages([buildWelcomeMsg(g)]);
  };

  const clearChat = async () => {
    const doClear = () => {
      // Preserve userGender across clear — show fresh welcome for the known gender,
      // or ask again if we somehow never stored one.
      setMessages([buildWelcomeMsg(userGender, true)]);
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
      .filter((m) => m.id !== "welcome" && m.id !== GENDER_SELECT_ID)
      .slice(-8)
      .map((m) => ({ role: m.role === "user" ? "user" : "assistant", text: m.text }));
    setMessages((m) => [...m, userMsg]);
    setLoading(true);
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);

    const botMsgId = `b-${Date.now()}`;
    let metaReceived = false;
    let accumulatedText = "";

    try {
      await new Promise<void>((resolve) => {
        const cancel = api.chatStream(
          text,
          {
            onMeta: (meta) => {
              if (meta?.session_id) setSessionId(meta.session_id);
              metaReceived = true;
              // Insert empty bot message right away — results render immediately
              const initialBot: Msg = {
                id: botMsgId,
                role: "bot",
                text: "",
                results: meta?.results || [],
                intent: meta?.intent,
              };
              setMessages((m) => [...m, initialBot]);
              setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 40);
            },
            onToken: (token) => {
              accumulatedText += token;
              setMessages((m) =>
                m.map((b) =>
                  b.id === botMsgId ? { ...b, text: accumulatedText } : b,
                ),
              );
            },
            onDone: (data) => {
              const finalReply = (data?.reply || accumulatedText || "").trim();
              const followUps =
                Array.isArray(data?.follow_ups) && data.follow_ups.length
                  ? data.follow_ups
                  : undefined;
              setMessages((m) =>
                m.map((b) =>
                  b.id === botMsgId
                    ? { ...b, text: finalReply || b.text, followUps }
                    : b,
                ),
              );
              setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 80);
              resolve();
            },
            onError: (err) => {
              console.warn("chat stream err", err);
              if (!metaReceived) {
                setMessages((m) => [
                  ...m,
                  { id: `b-${Date.now()}`, role: "bot", text: "מצטערים, משהו השתבש. נסו שוב." },
                ]);
              }
              resolve();
            },
          },
          { session_id: sessionId, history, user_gender: userGender ?? undefined },
        );
        // Safety timeout — 45s max
        setTimeout(() => {
          cancel();
          resolve();
        }, 45000);
      });
    } catch (e) {
      console.warn("chat err", e);
      setMessages((m) => [
        ...m,
        { id: `b-${Date.now()}`, role: "bot", text: "מצטערים, משהו השתבש. נסו שוב." },
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
              <Text style={styles.headerSub}>העוזרת המקומית שלך · תמיד כאן</Text>
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
                onPress={() => router.push("/sources")}
                style={({ pressed }) => [
                  styles.headerIconBtn,
                  pressed && { opacity: 0.6 },
                ]}
                accessibilityLabel="מקורות מידע"
                testID="header-sources"
              >
                <Ionicons name="information-circle-outline" size={20} color={COLORS.primary} />
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
                    {m.id === GENDER_SELECT_ID && (
                      <View style={styles.genderRow}>
                        <Pressable
                          onPress={() => pickGender("m")}
                          style={({ pressed }) => [
                            styles.genderChip,
                            pressed && { opacity: 0.75 },
                          ]}
                          testID="gender-male"
                        >
                          <Text style={styles.genderEmoji}>👨</Text>
                          <Text style={styles.genderText}>בלשון זכר</Text>
                        </Pressable>
                        <Pressable
                          onPress={() => pickGender("f")}
                          style={({ pressed }) => [
                            styles.genderChip,
                            pressed && { opacity: 0.75 },
                          ]}
                          testID="gender-female"
                        >
                          <Text style={styles.genderEmoji}>👩</Text>
                          <Text style={styles.genderText}>בלשון נקבה</Text>
                        </Pressable>
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
    width: 72,
    height: 72,
    alignItems: "center",
    justifyContent: "center",
  },
  mascotImg: {
    width: 72,
    height: 72,
  },
  mascotSmall: {
    width: 40,
    height: 40,
    alignItems: "center",
    justifyContent: "center",
    marginStart: 6,
  },
  mascotSmallImg: {
    width: 40,
    height: 40,
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

  genderRow: {
    flexDirection: "row-reverse",
    gap: 10,
    marginTop: 14,
  },
  genderChip: {
    flex: 1,
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(20,184,179,0.12)",
    borderWidth: 1.5,
    borderColor: "rgba(20,184,179,0.45)",
    minHeight: 46,
  },
  genderEmoji: { fontSize: 18 },
  genderText: { fontSize: 14, fontWeight: "800", color: COLORS.primary },

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
