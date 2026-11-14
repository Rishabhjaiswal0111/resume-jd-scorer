/**
 * UI switches. Flip a flag here to try a layout or feature without a branch.
 * Keep entries few and delete them once a decision is made.
 */
export const uiConfig = {
  appName: 'JD × Resume Scorer',
  /** Show the Debug tab (raw prompt / response / ledger) on run pages. */
  showDebugTools: import.meta.env.DEV,
  /**
   * TanStack Query devtools button (request/cache inspector). Off by default; turn on with
   * `VITE_SHOW_QUERY_DEVTOOLS=true make dev-web`. Never included in production builds.
   */
  showQueryDevtools: import.meta.env.DEV && import.meta.env.VITE_SHOW_QUERY_DEVTOOLS === 'true',
  /** How often the header polls API health, in ms. */
  healthPollMs: 30_000,
} as const
