import React, { useEffect, useMemo, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Image,
  TouchableOpacity,
  ActivityIndicator,
  Platform,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { openLink, formatHebrewTime } from "../../api";
import { COLORS, RADIUS, SPACING } from "../../theme";

type Article = {
  id: string;
  title: string;
  summary: string;
  content_html?: string;
  image?: string;
  source_name?: string;
  source_url?: string;
  source_type?: string;
  published_at: string;
};

// Convert raw HTML into a list of blocks: paragraphs (text), images, headings
type Block =
  | { kind: "text"; text: string; level?: number }
  | { kind: "image"; url: string };

function parseHtmlToBlocks(html: string): Block[] {
  if (!html) return [];
  // remove script / style / nav / header / footer / aside blocks entirely
  let h = html.replace(/<(script|style|nav|header|footer|aside)[\s\S]*?<\/\1>/gi, "");
  // extract images inline first via placeholder
  const blocks: Block[] = [];
  const imgRe = /<img[^>]*src=["']([^"']+)["'][^>]*>/gi;
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  const queue: Array<{ kind: "text" | "image"; value: string }> = [];
  while ((m = imgRe.exec(h))) {
    const before = h.slice(lastIdx, m.index);
    if (before.trim()) queue.push({ kind: "text", value: before });
    queue.push({ kind: "image", value: m[1] });
    lastIdx = m.index + m[0].length;
  }
  const tail = h.slice(lastIdx);
  if (tail.trim()) queue.push({ kind: "text", value: tail });

  for (const q of queue) {
    if (q.kind === "image") {
      const url = q.value;
      if (url.startsWith("http") || url.startsWith("//")) {
        blocks.push({ kind: "image", url: url.startsWith("//") ? "https:" + url : url });
      }
      continue;
    }
    // split text into paragraphs by block tags.
    // NOTE: Use non-capturing groups (?:...) — capturing groups in split()
    // cause the captured text ("div", "p" etc.) to appear as array entries!
    const chunks = q.value.split(/<\/(?:p|div|h[1-6]|li|br)[^>]*>|<br\s*\/?>|<!--[\s\S]*?-->/gi);
    for (const c of chunks) {
      if (!c) continue;
      let level: number | undefined;
      const hMatch = /<h([1-6])[^>]*>/i.exec(c);
      if (hMatch) level = parseInt(hMatch[1], 10);
      const clean = c
        .replace(/<!--[\s\S]*?-->/g, " ")
        .replace(/<[^>]+>/g, " ")
        .replace(/&nbsp;/g, " ")
        .replace(/&amp;/g, "&")
        .replace(/&quot;/g, '"')
        .replace(/&#39;|&apos;/g, "'")
        .replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">")
        .replace(/\s+/g, " ")
        .trim();
      if (clean.length > 1) blocks.push({ kind: "text", text: clean, level });
    }
  }
  return blocks;
}

export default function ArticleScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [article, setArticle] = useState<Article | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    (async () => {
      try {
        const url = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api/news/${id}`;
        const r = await fetch(url);
        if (r.ok) {
          const d = await r.json();
          setArticle(d);
        }
      } catch (e) {
        console.warn("load article", e);
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  const firstParagraph = useMemo(() => {
    const b = parseHtmlToBlocks(article?.content_html || "");
    const textBlock = b.find((x) => x.kind === "text" && (x as any).text && (x as any).text.length > 40) as
      | { kind: "text"; text: string }
      | undefined;
    return textBlock?.text || "";
  }, [article]);

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn} testID="article-back">
          <Ionicons name="chevron-forward" size={22} color={COLORS.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle} numberOfLines={1}>
          חדשות
        </Text>
        <View style={{ width: 40 }} />
      </View>

      {loading ? (
        <View style={{ paddingVertical: 60 }}>
          <ActivityIndicator color={COLORS.primary} />
        </View>
      ) : !article ? (
        <View style={styles.empty}>
          <Ionicons name="alert-circle-outline" size={40} color={COLORS.textMuted} />
          <Text style={styles.emptyText}>כתבה לא נמצאה</Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={{ paddingBottom: 120 }}>
          {article.image ? (
            <Image source={{ uri: article.image }} style={styles.hero} />
          ) : null}
          <View style={styles.body}>
            {article.source_name ? (
              <TouchableOpacity
                style={styles.sourcePill}
                onPress={() => article.source_url && openLink(article.source_url)}
                testID="article-source-pill"
              >
                <Ionicons name="open-outline" size={12} color={COLORS.accent} style={{ marginEnd: 4 }} />
                <Text style={styles.sourcePillText}>מקור: {article.source_name}</Text>
              </TouchableOpacity>
            ) : null}

            <Text style={styles.title}>{article.title}</Text>
            <Text style={styles.date}>{article.published_at ? formatHebrewTime(article.published_at) : ""}</Text>

            {article.summary ? <Text style={styles.summary}>{article.summary}</Text> : null}

            {firstParagraph ? (
              <Text style={styles.paragraph} selectable>
                {firstParagraph}
              </Text>
            ) : null}

            <TouchableOpacity
              style={styles.readAtSource}
              onPress={() => article.source_url && openLink(article.source_url)}
              testID="article-read-at-source"
            >
              <Ionicons name="open-outline" size={18} color="#fff" />
              <Text style={styles.readAtSourceText}>קרא את הכתבה המלאה</Text>
            </TouchableOpacity>

            <Text style={styles.disclaimer}>
              התוכן מתוך {article.source_name || "המקור המקורי"}. לקריאה מלאה — לחץ על הכפתור.
            </Text>
          </View>
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: COLORS.bg },
  topBar: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: SPACING.md,
    paddingVertical: SPACING.sm,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    backgroundColor: "#fff",
  },
  backBtn: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "rgba(15,23,42,0.04)",
  },
  topTitle: { color: COLORS.textPrimary, fontSize: 16, fontWeight: "800" },
  hero: { width: "100%", height: 240, backgroundColor: "#eee" },
  body: { padding: SPACING.lg },
  sourcePill: {
    alignSelf: "flex-end",
    flexDirection: "row-reverse",
    alignItems: "center",
    backgroundColor: "rgba(30,136,229,0.08)",
    borderWidth: 1,
    borderColor: "rgba(30,136,229,0.35)",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: RADIUS.pill,
  },
  sourcePillText: { color: COLORS.accent, fontSize: 12, fontWeight: "800" },
  title: {
    color: COLORS.textPrimary,
    fontSize: 26,
    fontWeight: "900",
    textAlign: "right",
    writingDirection: "rtl",
    marginTop: SPACING.md,
    lineHeight: 34,
  },
  date: { color: COLORS.textMuted, fontSize: 13, textAlign: "right", marginTop: 6 },
  summary: {
    color: COLORS.textSecondary,
    fontSize: 16,
    lineHeight: 24,
    marginTop: SPACING.md,
    textAlign: "right",
    writingDirection: "rtl",
    fontWeight: "500",
  },
  paragraph: {
    color: COLORS.textPrimary,
    fontSize: 16,
    lineHeight: 26,
    marginVertical: 8,
    textAlign: "right",
    writingDirection: "rtl",
  },
  heading: {
    fontSize: 20,
    fontWeight: "900",
    marginTop: 16,
  },
  inlineImage: {
    width: "100%",
    aspectRatio: 16 / 10,
    borderRadius: 12,
    marginVertical: 12,
    backgroundColor: "#eee",
  },
  readAtSource: {
    flexDirection: "row-reverse",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: COLORS.primary,
    paddingVertical: 14,
    borderRadius: RADIUS.md,
    marginTop: SPACING.lg,
    gap: 8,
  },
  readAtSourceText: { color: "#fff", fontWeight: "800", fontSize: 15 },
  disclaimer: {
    color: COLORS.textMuted,
    fontSize: 11,
    textAlign: "center",
    marginTop: SPACING.md,
    lineHeight: 16,
  },
  empty: { alignItems: "center", justifyContent: "center", paddingVertical: 60 },
  emptyText: { color: COLORS.textSecondary, marginTop: 10 },
});
