import { Toaster as Sonner } from "sonner";

import { useTheme } from "@/components/theme/ThemeProvider";

// Toast host. Sonner renders a single <Toaster/> near the root; anywhere in the
// app you call toast.success(...) / toast.error(...) and it shows here. We pass
// the current theme so toasts match light/dark mode.
export function Toaster() {
  const { theme } = useTheme();

  return (
    <Sonner
      theme={theme}
      className="toaster group"
      position="top-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-background group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
        },
      }}
    />
  );
}
