/**
 * Map a thrown error from `apiFetch` (or a raw `fetch`) to a user-friendly
 * message suitable for rendering inside `<EmptyState body={…}>` or similar.
 *
 * Audited 2026-05-18: 4 of 4 surfaces were leaking raw exception strings
 * ("Failed to fetch", "Error: policy log: 500", "GET /api/runtimes 500")
 * to the user-facing DOM. This helper exists so callers never have to.
 *
 * Returns an object so callers can pick whichever piece fits their layout:
 *   - title  short noun phrase suitable for an EmptyState title
 *   - body   one-sentence explanation in plain English
 *   - hint   optional next-step copy for advanced users
 *   - kind   discriminator for any caller-specific branching
 */
export type ApiErrorKind =
  | "offline"        // network failure — server unreachable
  | "unauthorized"   // 401 — not signed in
  | "forbidden"      // 403 — signed in but lacks permission
  | "not-found"      // 404 — resource missing
  | "server"         // 5xx — server fault
  | "client"         // other 4xx — request shape wrong
  | "unknown";       // anything we couldn't classify

export interface FriendlyApiError {
  kind: ApiErrorKind;
  title: string;
  body: string;
  hint?: string;
}

interface FetchLikeError {
  status?: number;
  message?: string;
  name?: string;
}

function isOfflineMessage(msg: string): boolean {
  const m = msg.toLowerCase();
  return (
    m.includes("failed to fetch") ||
    m.includes("networkerror") ||
    m.includes("err_connection_refused") ||
    m.includes("load failed") ||
    m.includes("network request failed")
  );
}

export function formatApiError(err: unknown): FriendlyApiError {
  if (err == null) {
    return { kind: "unknown", title: "Something's not right", body: "We hit an unexpected condition. Try again in a moment." };
  }

  // Object-shape: { status, message } — our apiFetch typically throws these.
  if (typeof err === "object") {
    const e = err as FetchLikeError;
    const status = e.status;
    const message = (e.message ?? "").toString();

    if (status === 401) {
      return {
        kind: "unauthorized",
        title: "You're signed out",
        body: "Sign in to load this surface.",
      };
    }
    if (status === 403) {
      return {
        kind: "forbidden",
        title: "Not your org",
        body: "Your account doesn't have access to this resource.",
      };
    }
    if (status === 404) {
      return {
        kind: "not-found",
        title: "Not found",
        body: "Whatever this page was loading isn't there. It may have been deleted or moved.",
      };
    }
    if (typeof status === "number" && status >= 500) {
      return {
        kind: "server",
        title: "Service hiccup",
        body: "The server returned an error. We retried; it's still failing. Try again in a moment.",
        hint: `HTTP ${status}`,
      };
    }
    if (typeof status === "number" && status >= 400) {
      return {
        kind: "client",
        title: "Request rejected",
        body: "The server refused this request. This is likely a bug — please report it.",
        hint: `HTTP ${status}`,
      };
    }
    if (message && isOfflineMessage(message)) {
      return {
        kind: "offline",
        title: "Service offline",
        body: "Can't reach the Crawfish server. If you're running locally, start cloud/server and refresh.",
      };
    }
    if (message) {
      return { kind: "unknown", title: "Something's not right", body: message };
    }
  }

  // String error
  if (typeof err === "string") {
    if (isOfflineMessage(err)) {
      return {
        kind: "offline",
        title: "Service offline",
        body: "Can't reach the Crawfish server. If you're running locally, start cloud/server and refresh.",
      };
    }
    return { kind: "unknown", title: "Something's not right", body: err };
  }

  return { kind: "unknown", title: "Something's not right", body: "We hit an unexpected condition. Try again in a moment." };
}
