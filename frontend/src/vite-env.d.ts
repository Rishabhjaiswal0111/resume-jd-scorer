/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" shows the TanStack Query devtools button (dev server only). */
  readonly VITE_SHOW_QUERY_DEVTOOLS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
