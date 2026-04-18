// Eilatush theme — aligned with Eilat Municipality brand identity
// (coral X-mark primary + Red Sea turquoise + clean light surfaces)
export const COLORS = {
  bg: "#F6F8FB",           // airy off-white backdrop
  surface: "#FFFFFF",       // clean surface
  card: "#FFFFFF",          // white cards
  cardHigh: "#F1F4F9",      // subtle alt card
  primary: "#E63946",       // Eilat coral/red (brand X-mark)
  primaryHover: "#F25561",  // hover/pressed coral
  secondary: "#14B8B3",     // Red Sea turquoise
  accent: "#1E88E5",        // sky blue accent
  textPrimary: "#0F172A",   // near-black for headlines
  textSecondary: "#475569", // body
  textMuted: "#94A3B8",     // muted meta
  border: "rgba(15, 23, 42, 0.08)",
  borderStrong: "rgba(15, 23, 42, 0.18)",
  success: "#22C55E",
  danger: "#E63946",
  whatsapp: "#25D366",
  overlay: "rgba(15,23,42,0.55)",
  onPrimary: "#FFFFFF",
  chipBg: "#FFFFFF",
  chipBgActive: "rgba(230, 57, 70, 0.08)",
};

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const RADIUS = {
  sm: 8,
  md: 12,
  lg: 18,
  xl: 24,
  pill: 999,
};

export const FONT = {
  family: "Heebo, Assistant, System, sans-serif",
  weightRegular: "400" as const,
  weightMedium: "500" as const,
  weightBold: "700" as const,
  weightBlack: "900" as const,
};

export const SHADOWS = {
  sm: {
    shadowColor: "#0F172A",
    shadowOpacity: 0.06,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
    elevation: 2,
  },
  md: {
    shadowColor: "#0F172A",
    shadowOpacity: 0.08,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },
};
