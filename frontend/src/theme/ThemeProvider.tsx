import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { accent, cssVars, DEFAULT_THEME, FONT_IMPORT, THEMES, type ThemeMode } from "./themes";

interface ThemeContextValue {
  preset: string;
  mode: ThemeMode;
  setPreset: (p: string) => void;
  setMode: (m: ThemeMode) => void;
  toggleMode: () => void;
  accentHex: string;
  presetNames: string[];
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const LS_PRESET = "lamata.theme.preset";
const LS_MODE = "lamata.theme.mode";

let fontLinkInjected = false;
function ensureFontLink() {
  if (fontLinkInjected) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = FONT_IMPORT;
  document.head.appendChild(link);
  fontLinkInjected = true;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preset, setPreset] = useState<string>(() => localStorage.getItem(LS_PRESET) || DEFAULT_THEME);
  const [mode, setMode] = useState<ThemeMode>(() => (localStorage.getItem(LS_MODE) as ThemeMode) || "dark");

  useEffect(() => {
    ensureFontLink();
  }, []);

  useEffect(() => {
    const vars = cssVars(preset, mode);
    const root = document.documentElement;
    Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v));
    root.classList.toggle("dark", mode === "dark");
    root.style.colorScheme = mode;
    localStorage.setItem(LS_PRESET, preset);
    localStorage.setItem(LS_MODE, mode);
  }, [preset, mode]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      preset,
      mode,
      setPreset,
      setMode,
      toggleMode: () => setMode((m) => (m === "dark" ? "light" : "dark")),
      accentHex: accent(preset, mode),
      presetNames: Object.keys(THEMES),
    }),
    [preset, mode]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
