const APP_BASE_URL = "https://app.candway.com";

export function appAuthUrl(
  path: "/auth/login" | "/auth/register",
  params?: Record<string, string | undefined>,
): string {
  const url = new URL(path, APP_BASE_URL);

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        url.searchParams.set(key, value);
      }
    }
  }

  return url.toString();
}
