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

// ─── Typed helpers ────────────────────────────────────────────────────────

export type AgentMeta = {
  name: string;
  role: string;
  runtime: string;
  hiredAt: string;
};

export type OrgMember = {
  email: string;
  name: string | null;
  role: string;
  createdAt: string;
};

export type Org = {
  id: string;
  name: string;
  project: string | null;
  teamSize: string | null;
  primaryClient: string | null;
  createdAt: string;
  agents: AgentMeta[];
  members: OrgMember[];
};

export type OrgSummary = Omit<Org, "agents" | "members"> & {
  role: string;
  memberCount: number;
  agentCount: number;
};

export type ApiError = Error & { code?: string; status?: number };

async function unwrap<T>(res: Response): Promise<T> {
  if (res.ok) return (await res.json()) as T;
  let code = "http_error";
  let message = `HTTP ${res.status}`;
  try {
    const body = await res.json();
    if (body?.error?.code) code = String(body.error.code);
    if (body?.error?.message) message = String(body.error.message);
  } catch {
    /* non-JSON body; fall through */
  }
  const err: ApiError = Object.assign(new Error(message), { code, status: res.status });
  throw err;
}

export type CreateOrgInput = {
  name: string;
  project?: string;
  teamSize?: string;
  primaryClient?: string;
  agents?: Array<Pick<AgentMeta, "name" | "role" | "runtime">>;
};

export async function createOrg(body: CreateOrgInput): Promise<Org> {
  const res = await apiFetch("/api/orgs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return unwrap<Org>(res);
}

export async function listMyOrgs(): Promise<OrgSummary[]> {
  const res = await apiFetch("/api/me/orgs");
  return unwrap<OrgSummary[]>(res);
}

export async function fetchOrg(id: string): Promise<Org> {
  const res = await apiFetch(`/api/orgs/${encodeURIComponent(id)}`);
  return unwrap<Org>(res);
}
