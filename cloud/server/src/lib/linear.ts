/**
 * Linear OAuth2 + GraphQL client.
 *
 * Bare `fetch`, no @linear/sdk — matches the github.ts house style.
 *
 * CRITICAL (RESEARCH Pitfall 1): Linear access tokens expire ~24h since
 * 2026-04-01, so the refresh token is mandatory. `graphql()` throws
 * `LinearTokenExpired` on HTTP 401 so the sync layer can refresh-and-retry.
 *
 * Env (read at call time, not module load, so tests can set dummies and a
 * missing config surfaces only when a connect is actually attempted):
 *   LINEAR_CLIENT_ID, LINEAR_CLIENT_SECRET, LINEAR_REDIRECT_URI
 */

const AUTHORIZE_URL = "https://linear.app/oauth/authorize";
const TOKEN_URL = "https://api.linear.app/oauth/token";
const GRAPHQL_URL = "https://api.linear.app/graphql";

export class LinearTokenExpired extends Error {
  constructor() {
    super("Linear access token expired (HTTP 401)");
  }
}

export class LinearNotConfigured extends Error {
  constructor(missing: string) {
    super(`Linear OAuth is not configured: ${missing} is unset`);
  }
}

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new LinearNotConfigured(name);
  return v;
}

export interface LinearTokens {
  access_token: string;
  refresh_token: string;
  expires_in?: number;
}

/** Build the authorize URL the browser is redirected to, carrying the CSRF state. */
export function buildAuthorizeUrl(state: string): string {
  const params = new URLSearchParams({
    client_id: requireEnv("LINEAR_CLIENT_ID"),
    redirect_uri: requireEnv("LINEAR_REDIRECT_URI"),
    response_type: "code",
    scope: "read",
    state,
  });
  return `${AUTHORIZE_URL}?${params.toString()}`;
}

/** Exchange an authorization code for an access + refresh token pair. */
export async function exchangeCode(code: string): Promise<LinearTokens> {
  const body = new URLSearchParams({
    client_id: requireEnv("LINEAR_CLIENT_ID"),
    client_secret: requireEnv("LINEAR_CLIENT_SECRET"),
    redirect_uri: requireEnv("LINEAR_REDIRECT_URI"),
    grant_type: "authorization_code",
    code,
  });
  const r = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!r.ok) throw new Error(`linear token exchange ${r.status}`);
  const j = (await r.json()) as LinearTokens;
  if (!j.access_token || !j.refresh_token) throw new Error("linear token response missing fields");
  return j;
}

/** Trade a refresh token for a fresh access + refresh pair. */
export async function refreshAccessToken(refreshToken: string): Promise<LinearTokens> {
  const body = new URLSearchParams({
    client_id: requireEnv("LINEAR_CLIENT_ID"),
    client_secret: requireEnv("LINEAR_CLIENT_SECRET"),
    grant_type: "refresh_token",
    refresh_token: refreshToken,
  });
  const r = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  if (!r.ok) throw new Error(`linear token refresh ${r.status}`);
  const j = (await r.json()) as LinearTokens;
  if (!j.access_token) throw new Error("linear refresh response missing access_token");
  // Linear may or may not rotate the refresh token; keep the old one if absent.
  return { access_token: j.access_token, refresh_token: j.refresh_token || refreshToken };
}

async function graphql<T>(
  token: string,
  query: string,
  variables?: Record<string, unknown>,
): Promise<T> {
  const r = await fetch(GRAPHQL_URL, {
    method: "POST",
    headers: { Authorization: token, "Content-Type": "application/json" },
    body: JSON.stringify({ query, variables: variables ?? {} }),
  });
  if (r.status === 401) throw new LinearTokenExpired();
  if (!r.ok) throw new Error(`linear graphql ${r.status}`);
  const j = (await r.json()) as { data?: T; errors?: unknown };
  if (j.errors) throw new Error(`linear graphql errors: ${JSON.stringify(j.errors)}`);
  if (j.data === undefined) throw new Error("linear graphql empty data");
  return j.data;
}

export interface LinearTeam {
  id: string;
  key: string;
  name: string;
}

export async function listTeams(token: string): Promise<LinearTeam[]> {
  const data = await graphql<{ teams: { nodes: LinearTeam[] } }>(
    token,
    `query { teams { nodes { id key name } } }`,
  );
  return data.teams.nodes;
}

export interface LinearIssueNode {
  id: string;
  identifier: string;
  title: string;
  description: string | null;
  url: string;
  updatedAt: string;
  state: { name: string; type: string };
  assignee: { displayName: string | null; email: string | null } | null;
  labels: { nodes: Array<{ name: string }> };
  project: { name: string } | null;
  cycle: { number: number } | null;
}

export interface LinearIssuePage {
  nodes: LinearIssueNode[];
  pageInfo: { hasNextPage: boolean; endCursor: string | null };
}

const TEAM_ISSUES_QUERY = `query TeamIssues($teamId: String!, $after: String) {
  team(id: $teamId) {
    issues(first: 50, after: $after) {
      nodes {
        id identifier title description url updatedAt
        state { name type }
        assignee { displayName email }
        labels { nodes { name } }
        project { name }
        cycle { number }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}`;

export async function listTeamIssues(
  token: string,
  teamId: string,
  after?: string,
): Promise<LinearIssuePage> {
  const data = await graphql<{ team: { issues: LinearIssuePage } }>(token, TEAM_ISSUES_QUERY, {
    teamId,
    after: after ?? null,
  });
  return data.team.issues;
}

/** Linear workflow-state type → our normalized open/closed. */
export function normalizeLinearState(stateType: string): "open" | "closed" {
  return stateType === "completed" || stateType === "canceled" ? "closed" : "open";
}
