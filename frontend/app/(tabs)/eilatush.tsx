import React, { useRef, useState } from "react";
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
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../api";
import { COLORS, RADIUS, SPACING } from "../../theme";
import { EventCard, BusinessCard, JobCard, NewsCard } from "../../components";

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
};

const SUGGESTIONS = [
  "מה קורה הערב?",
  "ברים פתוחים עכשיו",
  "עבודה דחופה",
  "סושי זול",
  "חדשות מהעירייה",
  "מסיבות הלילה",
];

export default function EilatushScreen() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: "welcome",
      role: "bot",
      text: "היי! אני אילתוש 🐠 \nשאל אותי מה קורה בעיר, איפה לאכול, איפה לעבוד או מה חדש. אני חוזר עם הכל בתוך שניות.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  const send = async (msg?: string) => {
    const text = (msg ?? input).trim();
    if (!text || loading) return;
    setInput("");
    const userMsg: Msg = { id: `u-${Date.now()}`, role: "user", text };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);
    setTimeout(() => scrollRef.current?.scrollToEnd({ animated: true }), 50);
    try {
      const res = await api.chat(text, sessionId);
      if (res.session_id) setSessionId(res.session_id);
      const botMsg: Msg = {
        id: `b-${Date.now()}`,
        role: "bot",
        text: res.reply || "הנה מה שמצאתי 🐠",
        results: res.results || [],
        intent: res.intent,
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
              <Ionicons name="sparkles" size={20} color="#fff" />
            </View>
            <View>
              <Text style={styles.headerTitle}>אילתוש</Text>
              <Text style={styles.headerSub}>העוזר המקומי שלך · תמיד כאן</Text>
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
                    <Ionicons name="sparkles" size={14} color="#fff" />
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
                    {m.id === "welcome" && (
                      <View style={styles.sugWrap}>
                        {SUGGESTIONS.map((s) => (
                          <Pressable
                            key={s}
                            onPress={() => send(s)}
                            style={({ pressed }) => [styles.sugChip, pressed && { opacity: 0.7 }]}
                            testID={`suggestion-${s}`}
                          >
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
                <Ionicons name="sparkles" size={14} color="#fff" />
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
    backgroundColor: COLORS.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: COLORS.primary,
    shadowOpacity: 0.5,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
  },
  mascotSmall: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: COLORS.primary,
    alignItems: "center",
    justifyContent: "center",
    marginStart: 8,
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
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: RADIUS.pill,
    backgroundColor: "rgba(20,184,179,0.10)",
    borderColor: "rgba(20,184,179,0.35)",
    borderWidth: 1,
  },
  sugChipText: { color: COLORS.secondary, fontSize: 13, fontWeight: "700" },

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
