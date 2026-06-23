import { Toaster as Sonner } from "sonner";

import { useTheme } from "@/components/theme/ThemeProvider";
import { sonnerTheme } from "@/lib/themes";

// Toast host. Sonner renders a single <Toaster/> near the root; anywhere in the
// app you call toast.success(...) / toast.error(...) and it shows here. Sonner only
// understands light/dark/system, so we map our extra palettes onto the closest one.
export function Toaster() {
  const { theme } = useTheme();

  return (
    <Sonner
      theme={sonnerTheme(theme)}
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
