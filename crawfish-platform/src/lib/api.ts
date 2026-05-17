/**
 * apiFetch — single entry point for talking to crawfish-server.
 *
 * Real auth: pulls a Clerk session JWT via window.Clerk?.session?.getToken()
 *            and sets Authorization: Bearer <token>.
 * Dev mode:  reads localStorage.cf_dev_user (default "dev-user") and sets
 *            X-User-Id — matches crawfish-server/src/middleware/auth.ts shim.
 */
import { CLERK_ENABLED, SERVER_URL } from "./clerk";

declare global {
  interface Window {
    Clerk?: {
      session?: { getToken: () => Promise<string | null> };
    };
  }
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const url = path.startsWith("http") ? path : `${SERVER_URL}${path.startsWith("/") ? "" : "/"}${path}`;
  const headers = new Headers(init.headers ?? {});

  if (CLERK_ENABLED) {
    try {
      const token = await window.Clerk?.session?.getToken();
      if (token) headers.set("Authorization", `Bearer ${token}`);
    } catch {
      /* swallow — request will go through unauthenticated and the server can 401 */
    }
  } else {
    const devUser =
      (typeof localStorage !== "undefined" && localStorage.getItem("cf_dev_user")) || "dev-user";
    headers.set("X-User-Id", devUser);
  }

  return fetch(url, { ...init, headers });
}
