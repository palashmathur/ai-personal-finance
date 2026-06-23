// Central theme registry. The app supports more than light/dark now — a set of
// soft, low-contrast palettes that are easier on the eyes for long sessions.
//
// How it works: each concrete theme is one or more CSS classes applied to <html>.
// The CSS variables for each live in index.css; Tailwind reads them via
// hsl(var(--token)). "system" follows the OS. The light-ish palettes apply only a
// `theme-*` class; the dark ones ALSO apply `dark` so Tailwind's `dark:` utilities
// still fire, with `theme-dim` layered on top to warm the dark palette.

export type ThemeName =
  | "system"
  | "light"
  | "dark"
  | "paper"
  | "sand"
  | "sage"
  | "dim";

export interface ThemeMeta {
  name: ThemeName;
  label: string;
  // A small CSS background value used as a preview dot in the picker.
  swatch: string;
}

// Order shown in the theme picker.
export const THEMES: ThemeMeta[] = [
  { name: "system", label: "System", swatch: "linear-gradient(135deg,#ffffff 50%,#0a0f1a 50%)" },
  { name: "light", label: "Light", swatch: "#ffffff" },
  { name: "dark", label: "Dark", swatch: "#0a0f1a" },
  { name: "paper", label: "Paper (off-white)", swatch: "#faf8f1" },
  { name: "sand", label: "Sand (beige)", swatch: "#efe6d4" },
  { name: "sage", label: "Sage (green)", swatch: "#eef2ea" },
  { name: "dim", label: "Dim (warm dark)", swatch: "#26221e" },
];

// A concrete theme is everything except "system" (which resolves to light/dark).
type ConcreteTheme = Exclude<ThemeName, "system">;

// The <html> classes that turn each concrete theme on.
export const THEME_CLASSES: Record<ConcreteTheme, string[]> = {
  light: [], // :root defaults
  dark: ["dark"],
  paper: ["theme-paper"],
  sand: ["theme-sand"],
  sage: ["theme-sage"],
  dim: ["dark", "theme-dim"], // `dark` so dark: utilities apply; theme-dim warms it
};

// Every class we might add — removed before applying a new theme so switches are clean.
export const ALL_THEME_CLASSES = ["dark", "theme-paper", "theme-sand", "theme-sage", "theme-dim"];

// Which concrete themes are dark — used to tell sonner (toasts) which mode to use.
const DARK_THEMES = new Set<ConcreteTheme>(["dark", "dim"]);

// Resolve a stored theme (possibly "system") to its concrete name given the OS.
export function resolveTheme(theme: ThemeName, prefersDark: boolean): ConcreteTheme {
  if (theme === "system") return prefersDark ? "dark" : "light";
  return theme;
}

// sonner only understands light | dark | system — map our palettes onto that.
export function sonnerTheme(theme: ThemeName): "light" | "dark" | "system" {
  if (theme === "system") return "system";
  return DARK_THEMES.has(theme) ? "dark" : "light";
}
