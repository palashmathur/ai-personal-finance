import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite config. The `@` alias maps to `src/` so imports read `@/components/...`
// instead of long relative chains (`../../../components`). shadcn/ui assumes
// this alias exists — it must match the `paths` entry in tsconfig.json.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // PF-F1 locks the dev server to 5173 (the value CORS on the backend expects).
    port: 5173,
    strictPort: true,
  },
});
