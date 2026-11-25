export type ApiConnectionStatus = "connected" | "unavailable";

export function checkApiHealth(
  baseUrl: string,
  fetchImpl?: typeof fetch,
): Promise<ApiConnectionStatus>;
