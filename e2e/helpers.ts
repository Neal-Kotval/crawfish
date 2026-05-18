/**
 * Cross-suite test helpers.
 *
 * Auth model:
 *   - The platform server (7882) uses dev-mode auth that reads X-User-Id and
 *     X-User-Email headers. Tests use that shim to mint disposable identities
 *     for API-side seeding regardless of whether the platform frontend has
 *     Clerk turned on.
 *   - The platform frontend (5174) gates routes behind RequireAuth. When
 *     VITE_CLERK_PUBLISHABLE_KEY is set in crawfish-platform/.env, the
 *     dev-mode browser path (localStorage.cf_dev_user) is bypassed and the
 *     guard demands a real Clerk session. Tests that walk the signed-in
 *     UI surface guard on `expectDevMode()` and skip when Clerk is on.
 *
 * Dash (7881) gates its UI on a localStorage key cf-linked-user; helpers
 * here let tests seed/clear that key before navigation.
 */
import type { Page, APIRequestContext } from "@playwright/test";

export const PLATFORM_URL = "http://localhost:5174";
export const DASH_URL = "http://localhost:7881";
export const DASH_API = "http://localhost:7880";
export const SERVER_URL = "http://localhost:7882";

export type ServerOrg = {
  id: string;
  name: string;
  project: string | null;
  teamSize: string | null;
  primaryClient: string | null;
  createdAt: string;
  agents: Array<{ name: string; role: string; runtime: string; hiredAt: string }>;
  members: Array<{ email: string; name: string | null; role: string; createdAt: string }>;
};

export type ServerInvite = {
  id: string;
  email: string;
  role: "owner" | "contributor";
  code: string;
  expiresAt: string;
  mockEmail: { to: string; subject: string; link: string };
};

function devHeaders(userId: string, email?: string): Record<string, string> {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    "X-User-Id": userId,
    "Cookie": "",
  };
  if (email) h["X-User-Email"] = email;
  return h;
}

export async function apiCreateOrg(
  request: APIRequestContext,
  args: {
    name: string;
    userId: string;
    email?: string;
    project?: string;
    teamSize?: "Just me" | "2–5" | "5–20" | "20+";
    primaryClient?: "Dash" | "CLI" | "IDE" | "All three";
  },
): Promise<ServerOrg> {
  const { name, userId, email, project, teamSize, primaryClient } = args;
  const res = await request.post(`${SERVER_URL}/api/orgs`, {
    headers: devHeaders(userId, email),
    data: {
      name,
      ...(project ? { project } : {}),
      ...(teamSize ? { teamSize } : {}),
      ...(primaryClient ? { primaryClient } : {}),
    },
  });
  if (!res.ok()) {
    throw new Error(`apiCreateOrg failed: ${res.status()} ${await res.text()}`);
  }
  return (await res.json()) as ServerOrg;
}

export async function apiCreateInvite(
  request: APIRequestContext,
  args: {
    orgId: string;
    email: string;
    userId: string;
    userEmail?: string;
    role?: "owner" | "contributor";
  },
): Promise<ServerInvite> {
  const res = await request.post(`${SERVER_URL}/api/orgs/${args.orgId}/invites`, {
    headers: devHeaders(args.userId, args.userEmail),
    data: { email: args.email, role: args.role ?? "contributor" },
  });
  if (!res.ok()) {
    throw new Error(`apiCreateInvite failed: ${res.status()} ${await res.text()}`);
  }
  return (await res.json()) as ServerInvite;
}

/**
 * Detect whether the platform frontend boots in Clerk mode by inspecting
 * what the root route does. In dev mode (no Clerk) the OrgPicker renders
 * with "Your orgs". In Clerk mode RequireAuth bounces to /signin.
 *
 * Cached per worker so we only pay the cost once.
 */
let _devModeCache: boolean | null = null;
export async function isPlatformDevMode(page: Page): Promise<boolean> {
  if (_devModeCache !== null) return _devModeCache;
  await page.goto(`${PLATFORM_URL}/`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(500);
  const url = page.url();
  _devModeCache = !/\/signin/.test(url);
  return _devModeCache;
}

export async function clearDashIdentity(page: Page): Promise<void> {
  await page.goto(`${DASH_URL}/`);
  await page.evaluate(() => localStorage.removeItem("cf-linked-user"));
}

export async function seedDashIdentity(
  page: Page,
  email: string,
  name: string,
): Promise<void> {
  await page.goto(`${DASH_URL}/`);
  await page.evaluate(
    ({ e, n }) =>
      localStorage.setItem("cf-linked-user", JSON.stringify({ email: e, name: n })),
    { e: email, n: name },
  );
}

/** Set the platform's dev-mode user identity in localStorage. Caller must
 *  goto a platform URL first so the localStorage origin matches. */
export async function setPlatformDevUser(page: Page, email: string): Promise<void> {
  await page.goto(`${PLATFORM_URL}/onboarding`); // public route always renders
  await page.evaluate((e) => localStorage.setItem("cf_dev_user", e), email);
}

/** Create a local dash org via the dash node API (port 7880). All four
 *  fields are required by the server. */
export async function dashCreateLocalOrg(
  request: APIRequestContext,
  args: { name: string; project?: string; teamSize?: string; primaryClient?: string },
): Promise<{ id: string; name: string }> {
  const res = await request.post(`${DASH_API}/api/orgs`, {
    data: {
      name: args.name,
      project: args.project ?? "e2e test project",
      teamSize: args.teamSize ?? "Just me",
      primaryClient: args.primaryClient ?? "Dash",
    },
  });
  if (!res.ok()) {
    throw new Error(`dashCreateLocalOrg failed: ${res.status()} ${await res.text()}`);
  }
  return (await res.json()) as { id: string; name: string };
}

/** Stable, slug-safe random suffix used for org names. */
export function rnd(): string {
  return Math.random().toString(36).slice(2, 8);
}
