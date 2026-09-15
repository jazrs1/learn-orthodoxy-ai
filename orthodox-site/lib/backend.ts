import "server-only";

/**
 * Server-side helper for talking to the FastAPI backend.
 *
 * - The backend URL comes from ORTHODOX_API_URL only. It is deliberately NOT a
 *   NEXT_PUBLIC_ variable: the browser never talks to the backend directly, so the
 *   URL should not be shipped in the client bundle.
 * - Every request carries the shared secret in X-Internal-Key. The backend rejects
 *   requests without it, so only these server routes (not arbitrary internet
 *   clients) can spend OpenAI credit.
 * - The end user's IP is forwarded in X-Client-IP so the backend can rate limit per
 *   user instead of per Vercel egress IP.
 */

export const BACKEND_NOT_CONFIGURED_MESSAGE =
  "The backend API URL is not configured. Set ORTHODOX_API_URL.";

export function backendUrl() {
  const value = process.env.ORTHODOX_API_URL || "";
  return value.trim().replace(/\/+$/, "");
}

export function backendConfigError(): string | null {
  if (!backendUrl()) return BACKEND_NOT_CONFIGURED_MESSAGE;
  if (!process.env.ORTHODOX_API_KEY) {
    return "The backend API key is not configured. Set ORTHODOX_API_KEY.";
  }
  return null;
}

export function clientIpFromRequest(request: Request): string {
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) return forwardedFor.split(",")[0]?.trim() || "unknown";
  return request.headers.get("x-real-ip") || "unknown";
}

export function backendHeaders(request?: Request, extra: Record<string, string> = {}) {
  const headers: Record<string, string> = {
    "X-Internal-Key": process.env.ORTHODOX_API_KEY || "",
    ...extra,
  };
  if (request) {
    headers["X-Client-IP"] = clientIpFromRequest(request);
  }
  return headers;
}

export async function backendFetch(
  path: string,
  init: RequestInit & { request?: Request; timeoutMs?: number } = {}
) {
  const { request, timeoutMs = 20000, headers, ...rest } = init;
  const url = path.startsWith("http") ? path : `${backendUrl()}${path}`;
  return fetch(url, {
    ...rest,
    headers: {
      ...backendHeaders(request),
      ...(headers as Record<string, string> | undefined),
    },
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });
}
