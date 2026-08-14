import type { Config } from "tailwindcss";

// Every color below reads from a CSS custom property defined in
// src/theme/themes.ts (ported 1:1 from the Streamlit app's themes.py),
// so Tailwind utility classes stay theme-aware across all 4 presets x
// light/dark without any per-component overrides.
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: "var(--font-display)",
        body: "var(--font-body)",
        mono: "var(--font-mono)",
      },
      colors: {
        app: "var(--bg-app)",
        card: "var(--bg-card)",
        card2: "var(--bg-card2)",
        sidebar: "var(--sidebar-bg)",
        border: "var(--border)",
        border2: "var(--border2)",
        "text-prim": "var(--text-prim)",
        "text-sec": "var(--text-sec)",
        "text-tert": "var(--text-tert)",
        accent: "var(--accent)",
        accent2: "var(--accent2)",
        good: "var(--badge-good-text)",
        "good-bg": "var(--badge-good-bg)",
        monitor: "var(--badge-mon-text)",
        "monitor-bg": "var(--badge-mon-bg)",
        over: "var(--badge-over-text)",
        "over-bg": "var(--badge-over-bg)",
      },
      borderRadius: {
        DEFAULT: "6px",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        "slide-up": "slide-up 0.25s ease-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
