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

export type ProjectSummary = {
  id: string;
  orgId: string;
  name: string;
  githubRepo: string | null;
  githubRepoId: number | null;
  defaultBranch: string | null;
  isPrivate: boolean;
  cloneStatus: "local_only" | "cloning" | "cloned" | "error";
  cloneError: string | null;
  localPath: string | null;
  deviceId: string | null;
  createdAt: string;
  updatedAt: string;
};

export async function listProjects(orgId: string): Promise<ProjectSummary[]> {
  const res = await apiFetch(`/api/orgs/${encodeURIComponent(orgId)}/projects`);
  return unwrap<ProjectSummary[]>(res);
}

export async function fetchOrg(id: string): Promise<Org> {
  const res = await apiFetch(`/api/orgs/${encodeURIComponent(id)}`);
  return unwrap<Org>(res);
}

// ─── Integrations & Issues ──────────────────────────────────────────────────

export type IntegrationProvider = "github" | "linear";

export type Integration = {
  provider: IntegrationProvider;
  connected: boolean;
  externalWorkspaceName: string | null;
};

export type LinearTeam = { id: string; key: string; name: string };

export type Issue = {
  id: string;
  provider: string;
  externalKey: string;
  number: number | null;
  title: string;
  state: "open" | "closed";
  url: string | null;
  labels: string[]; // server parses the JSON-encoded column for us
  assigneeExternal: string | null;
  externalUpdatedAt: string | null;
  syncedAt: string;
};

export type SyncResult = { provider: IntegrationProvider; synced: number };

export async function listIntegrations(orgId: string): Promise<Integration[]> {
  const res = await apiFetch(`/api/orgs/${encodeURIComponent(orgId)}/integrations`);
  return unwrap<Integration[]>(res);
}

export async function connectProvider(
  orgId: string,
  provider: "linear",
): Promise<{ authorizeUrl: string }> {
  const res = await apiFetch(
    `/api/orgs/${encodeURIComponent(orgId)}/integrations/${provider}/connect`,
    { method: "POST" },
  );
  return unwrap<{ authorizeUrl: string }>(res);
}

export async function listLinearTeams(orgId: string): Promise<LinearTeam[]> {
  const res = await apiFetch(`/api/orgs/${encodeURIComponent(orgId)}/integrations/linear/teams`);
  return unwrap<LinearTeam[]>(res);
}

export async function selectLinearTeam(
  orgId: string,
  body: { projectId: string; teamId: string; teamKey: string },
): Promise<unknown> {
  const res = await apiFetch(
    `/api/orgs/${encodeURIComponent(orgId)}/integrations/linear/select-team`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  return unwrap<unknown>(res);
}

export async function listIssues(orgId: string, projectId: string): Promise<Issue[]> {
  const res = await apiFetch(
    `/api/orgs/${encodeURIComponent(orgId)}/projects/${encodeURIComponent(projectId)}/issues`,
  );
  return unwrap<Issue[]>(res);
}

export async function syncProject(orgId: string, projectId: string): Promise<SyncResult> {
  const res = await apiFetch(
    `/api/orgs/${encodeURIComponent(orgId)}/projects/${encodeURIComponent(projectId)}/sync`,
    { method: "POST" },
  );
  return unwrap<SyncResult>(res);
}

// ─── Invites ──────────────────────────────────────────────────────────────

export type InviteRole = "owner" | "contributor";

export type Invite = {
  id: string;
  email: string;
  role: InviteRole;
  createdAt: string;
  expiresAt: string;
  code?: string;
};

export type MockEmail = { to: string; subject: string; link: string };

export type CreateInviteResponse = {
  id: string;
  email: string;
  role: InviteRole;
  code: string;
  expiresAt: string;
  mockEmail: MockEmail;
};

export type InvitePreview = {
  org: { id: string; name: string };
  email: string;
  role: InviteRole;
  expiresAt: string;
};

export async function createInvite(
  orgId: string,
  body: { email: string; role?: InviteRole },
): Promise<CreateInviteResponse> {
  const res = await apiFetch(`/api/orgs/${encodeURIComponent(orgId)}/invites`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return unwrap<CreateInviteResponse>(res);
}

export async function listInvites(orgId: string): Promise<Invite[]> {
  const res = await apiFetch(`/api/orgs/${encodeURIComponent(orgId)}/invites`);
  return unwrap<Invite[]>(res);
}

export async function revokeInvite(orgId: string, inviteId: string): Promise<void> {
  const res = await apiFetch(
    `/api/orgs/${encodeURIComponent(orgId)}/invites/${encodeURIComponent(inviteId)}`,
    { method: "DELETE" },
  );
  if (!res.ok && res.status !== 204) {
    await unwrap<unknown>(res); // throws ApiError
  }
}

export async function getInvite(code: string): Promise<InvitePreview> {
  // Public endpoint — apiFetch will still attach dev/Clerk headers, which is harmless.
  const res = await apiFetch(`/api/invites/${encodeURIComponent(code)}`);
  return unwrap<InvitePreview>(res);
}

export async function acceptInvite(
  code: string,
): Promise<{ org: { id: string; slug: string; name: string } }> {
  const res = await apiFetch(`/api/invites/${encodeURIComponent(code)}/accept`, {
    method: "POST",
  });
  return unwrap<{ org: { id: string; slug: string; name: string } }>(res);
}
