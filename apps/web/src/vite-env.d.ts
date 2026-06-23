/// <reference types="vite/client" />

// Typed access to import.meta.env.VITE_API_URL. Without this declaration TS
// treats every env var as `string | undefined` with no autocomplete. Think of
// it as declaring the shape of a properties file so the compiler knows the keys.
interface ImportMetaEnv {
  readonly VITE_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
