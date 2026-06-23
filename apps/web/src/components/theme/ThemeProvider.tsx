import { createContext, useContext, useEffect, useState } from "react";

import {
  ALL_THEME_CLASSES,
  resolveTheme,
  THEME_CLASSES,
  type ThemeName,
} from "@/lib/themes";

// Theme provider. Holds the selected theme in React context + localStorage and
// applies the right CSS class(es) to <html> (see themes.ts for the mapping). The
// CSS variables in index.css then repaint the whole app — no component changes.
// Context here is React's built-in dependency injection: provide a value at the
// top, read it anywhere below with the useTheme() hook.

type ThemeProviderState = {
  theme: ThemeName;
  setTheme: (theme: ThemeName) => void;
};

const ThemeProviderContext = createContext<ThemeProviderState>({
  theme: "system",
  setTheme: () => null,
});

export function ThemeProvider({
  children,
  defaultTheme = "system",
  storageKey = "pf-theme",
}: {
  children: React.ReactNode;
  defaultTheme?: ThemeName;
  storageKey?: string;
}) {
  const [theme, setThemeState] = useState<ThemeName>(
    () => (localStorage.getItem(storageKey) as ThemeName) || defaultTheme
  );

  // Apply the theme's class(es) whenever it changes. When set to "system" we also
  // subscribe to OS light/dark changes so the app follows them live.
  useEffect(() => {
    const root = window.document.documentElement;
    const mql = window.matchMedia("(prefers-color-scheme: dark)");

    const apply = () => {
      root.classList.remove(...ALL_THEME_CLASSES);
      const concrete = resolveTheme(theme, mql.matches);
      THEME_CLASSES[concrete].forEach((c) => root.classList.add(c));
    };

    apply();
    if (theme === "system") {
      mql.addEventListener("change", apply);
      return () => mql.removeEventListener("change", apply);
    }
  }, [theme]);

  const value: ThemeProviderState = {
    theme,
    setTheme: (next) => {
      localStorage.setItem(storageKey, next);
      setThemeState(next);
    },
  };

  return (
    <ThemeProviderContext.Provider value={value}>
      {children}
    </ThemeProviderContext.Provider>
  );
}

// Hook to read/update the theme from any component.
export function useTheme() {
  const context = useContext(ThemeProviderContext);
  if (context === undefined)
    throw new Error("useTheme must be used within a ThemeProvider");
  return context;
}
