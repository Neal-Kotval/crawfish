import { createClerkClient, type ClerkClient } from "@clerk/backend";

export class GithubNotConnected extends Error {
  constructor() {
    super("GitHub connection missing or revoked");
  }
}

let cached: ClerkClient | null = null;

export function getClerkClient(): ClerkClient {
  if (cached) return cached;
  cached = createClerkClient({ secretKey: process.env.CLERK_SECRET_KEY ?? "" });
  return cached;
}

/**
 * For tests: inject a stub client. Pass null to reset.
 */
export function _setClerkClientForTests(stub: ClerkClient | null): void {
  cached = stub;
}

export async function getGithubToken(userId: string): Promise<string> {
  const client = getClerkClient();
  const res = await client.users.getUserOauthAccessToken(userId, "oauth_github");
  const token = res.data?.[0]?.token;
  if (!token) throw new GithubNotConnected();
  return token;
}

export interface RepoMetadata {
  id: number;
  full_name: string;
  default_branch: string;
  private: boolean;
}

export async function fetchRepoMetadata(token: string, repoId: number): Promise<RepoMetadata> {
  const r = await fetch(`https://api.github.com/repositories/${repoId}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
  });
  if (!r.ok) throw new Error(`github ${r.status}`);
  const j = (await r.json()) as RepoMetadata;
  return { id: j.id, full_name: j.full_name, default_branch: j.default_branch, private: j.private };
}

export interface RepoSummary {
  id: number;
  full_name: string;
  default_branch: string;
  private: boolean;
  updated_at: string;
}

export class GithubRepoNotFound extends Error {
  constructor() {
    super("GitHub repository not found or inaccessible");
  }
}

export async function fetchRepoByName(
  token: string,
  owner: string,
  name: string,
): Promise<RepoMetadata> {
  const r = await fetch(
    `https://api.github.com/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`,
    {
      headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
    },
  );
  if (r.status === 404) throw new GithubRepoNotFound();
  if (!r.ok) throw new Error(`github ${r.status}`);
  const j = (await r.json()) as RepoMetadata;
  return { id: j.id, full_name: j.full_name, default_branch: j.default_branch, private: j.private };
}

export interface GithubIssue {
  node_id: string;
  number: number;
  title: string;
  body: string | null;
  state: string; // "open" | "closed"
  html_url: string;
  labels: Array<{ name?: string } | string>;
  assignee: { login: string } | null;
  updated_at: string;
  // Present ONLY on pull requests. The /issues endpoint returns PRs too, so
  // its presence is how we exclude them.
  pull_request?: unknown;
}

/**
 * List a repo's issues (state=all), excluding pull requests. Single page of up
 * to 100; callers paginate by incrementing `page` until a short page returns.
 */
export async function listRepoIssues(
  token: string,
  fullName: string,
  page = 1,
): Promise<GithubIssue[]> {
  const url = `https://api.github.com/repos/${fullName}/issues?state=all&per_page=100&page=${page}`;
  const r = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "crawfish-server",
    },
  });
  if (!r.ok) throw new Error(`github ${r.status}`);
  const arr = (await r.json()) as GithubIssue[];
  return arr.filter((i) => i.pull_request === undefined);
}

export async function listUserRepos(token: string, page: number): Promise<RepoSummary[]> {
  const url = `https://api.github.com/user/repos?sort=updated&per_page=30&page=${page}`;
  const r = await fetch(url, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
  });
  if (!r.ok) throw new Error(`github ${r.status}`);
  const arr = (await r.json()) as RepoSummary[];
  return arr.map((j) => ({
    id: j.id,
    full_name: j.full_name,
    default_branch: j.default_branch,
    private: j.private,
    updated_at: j.updated_at,
  }));
}
