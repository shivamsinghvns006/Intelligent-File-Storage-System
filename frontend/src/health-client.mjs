const HEALTH_TIMEOUT_MS = 3000;

export async function checkApiHealth(baseUrl, fetchImpl = globalThis.fetch) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);

  try {
    const response = await fetchImpl(new URL("/health", baseUrl), {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) return "unavailable";

    const body = await response.json();
    return body?.status === "ok" ? "connected" : "unavailable";
  } catch {
    return "unavailable";
  } finally {
    clearTimeout(timeoutId);
  }
}
