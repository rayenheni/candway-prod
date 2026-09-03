// Runtime configuration is centralized so production-sensitive switches are
// not reimplemented throughout the component tree.
export const runtimeConfig = {
  apiBaseUrl: import.meta.env.VITE_API_URL || '/api/v1',
  wsBaseUrl: import.meta.env.VITE_WS_URL || '',
  appName: import.meta.env.VITE_APP_NAME || 'Candway',
  demoMode: import.meta.env.VITE_DEMO_MODE === 'true',
  requestTimeoutMs: Number(import.meta.env.VITE_REQUEST_TIMEOUT_MS || 15_000),
} as const;
