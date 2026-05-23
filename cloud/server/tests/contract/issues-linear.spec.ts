import { describe, it, expect, beforeEach, afterAll } from "vitest";
import request from "supertest";

// linear.ts reads these at call time — set before importing the app.
process.env.LINEAR_CLIENT_ID = "lc_test";
process.env.LINEAR_CLIENT_SECRET = "ls_test";
process.env.LINEAR_REDIRECT_URI = "http://localhost:7882/api/integrations/linear/callback";

import { app, db } from "../../src/index.js";
import { signOrgToken, signOauthState, verifyOauthState } from "../../src/lib/jwt.js";

const realFetch = globalThis.fetch;
afterAll(() => {
  globalThis.fetch = realFetch;
});

function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const TOKEN_RESPONSE = {
  access_token: "lin_access_1",
  refresh_token: "lin_refresh_1",
  expires_in: 86400,
};

function teamIssuesPayload(nodes: unknown[]) {
  return { data: { team: { issues: { nodes, pageInfo: { hasNextPage: false, endCursor: null } } } } };
}

const SAMPLE_NODES = [
  {
    id: "lin_node_1",
    identifier: "ENG-123",
    title: "Fix the widget",
    description: "it is broken",
    url: "https://linear.app/acme/issue/ENG-123",
    updatedAt: "2026-05-10T00:00:00.000Z",
    state: { name: "Todo", type: "unstarted" },
    assignee: { displayName: "Dana", email: "dana@acme.dev" },
    labels: { nodes: [{ name: "bug" }] },
    project: { name: "Q2 Launch" },
    cycle: { number: 7 },
  },
  {
    id: "lin_node_2",
    identifier: "ENG-124",
    title: "Ship it",
    description: null,
    url: "https://linear.app/acme/issue/ENG-124",
    updatedAt: "2026-05-09T00:00:00.000Z",
    state: { name: "Done", type: "completed" },
    assignee: null,
    labels: { nodes: [] },
    project: null,
    cycle: null,
  },
];

let orgId: string;
let userId: string;

beforeEach(async () => {
  await db.issue.deleteMany({});
  await db.integration.deleteMany({});
  await db.project.deleteMany({});
  await db.orgMember.deleteMany({});
  await db.org.deleteMany({ where: { name: "linacme" } });

  const founder = await db.user.upsert({
    where: { email: "linacme-founder@local" },
    update: {},
    create: { email: "linacme-founder@local", name: "linacme-founder" },
  });
  userId = founder.id;
  const org = await db.org.create({ data: { name: "linacme" } });
  orgId = org.id;
  await db.orgMember.create({ data: { orgId, userId, role: "founder" } });
  globalThis.fetch = realFetch;
});

describe("linear connect returns an authorize URL carrying a signed state", () => {
  it("builds an authorize URL with the expected params and a verifiable state", async () => {
    const res = await request(app)
      .post(`/api/orgs/${orgId}/integrations/linear/connect`)
      .set("X-User-Id", "linacme-founder");
    expect(res.status).toBe(200);
    const url = new URL(res.body.authorizeUrl);
    expect(url.origin + url.pathname).toBe("https://linear.app/oauth/authorize");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("scope")).toBe("read");
    const state = url.searchParams.get("state")!;
    const decoded = verifyOauthState(state);
    expect(decoded).toMatchObject({ sub: userId, orgId, provider: "linear" });
  });

  it("oauth state audience is separate: a dash-sync token cannot pass as oauth-state", () => {
    const dashToken = signOrgToken(userId, orgId);
    expect(() => verifyOauthState(dashToken)).toThrow();
    // and a fresh oauth-state token round-trips
    expect(verifyOauthState(signOauthState(userId, orgId, "linear")).provider).toBe("linear");
  });
});

describe("oauth callback stores an Integration with a refresh token", () => {
  it("valid signed state + code → Integration row with refreshToken; redirects", async () => {
    globalThis.fetch = (async () => json(TOKEN_RESPONSE)) as typeof fetch;
    const state = signOauthState(userId, orgId, "linear");
    const res = await request(app)
      .get(`/api/integrations/linear/callback?code=abc123&state=${encodeURIComponent(state)}`);
    expect(res.status).toBe(302);
    const row = await db.integration.findUnique({
      where: { orgId_provider: { orgId, provider: "linear" } },
    });
    expect(row).not.toBeNull();
    expect(row!.refreshToken).toBe("lin_refresh_1");
    expect(row!.accessToken).toBe("lin_access_1");
  });

  it("tampered/expired state → 400 invalid_state and stores nothing (CSRF guard)", async () => {
    let fetchCalled = false;
    globalThis.fetch = (async () => {
      fetchCalled = true;
      return json(TOKEN_RESPONSE);
    }) as typeof fetch;
    const res = await request(app)
      .get(`/api/integrations/linear/callback?code=abc123&state=not-a-real-jwt`);
    expect(res.status).toBe(400);
    expect(res.body.error.code).toBe("invalid_state");
    expect(fetchCalled).toBe(false); // no token exchange on bad state
    expect(await db.integration.count({ where: { orgId } })).toBe(0);
  });

  it("GET …/integrations never returns tokens", async () => {
    await db.integration.create({
      data: { orgId, provider: "linear", accessToken: "secret_a", refreshToken: "secret_r" },
    });
    const res = await request(app)
      .get(`/api/orgs/${orgId}/integrations`)
      .set("X-User-Id", "linacme-founder");
    expect(res.status).toBe(200);
    const blob = JSON.stringify(res.body);
    expect(blob).not.toContain("secret_a");
    expect(blob).not.toContain("secret_r");
    const linear = res.body.find((p: { provider: string }) => p.provider === "linear");
    expect(linear).toMatchObject({ provider: "linear", connected: true });
  });
});

describe("team mapping: bound linearTeamId drives which team's issues sync; externalKey is ENG-###", () => {
  it("syncs the bound team's issues with ENG-### keys and metadata", async () => {
    await db.integration.create({
      data: { orgId, provider: "linear", accessToken: "lin_access_1", refreshToken: "lin_refresh_1" },
    });
    const project = await db.project.create({
      data: { orgId, name: "p", linearTeamId: "team_eng", linearTeamKey: "ENG", createdById: userId },
    });

    let sentTeamId: string | undefined;
    globalThis.fetch = (async (_url: string, init: RequestInit) => {
      const parsed = JSON.parse(String(init.body)) as { variables?: { teamId?: string } };
      sentTeamId = parsed.variables?.teamId;
      return json(teamIssuesPayload(SAMPLE_NODES));
    }) as unknown as typeof fetch;

    const res = await request(app)
      .post(`/api/orgs/${orgId}/projects/${project.id}/sync`)
      .set("X-User-Id", "linacme-founder");
    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ provider: "linear", synced: 2 });
    expect(sentTeamId).toBe("team_eng"); // the bound team drove the query

    const rows = await db.issue.findMany({ where: { projectId: project.id }, orderBy: { externalKey: "asc" } });
    expect(rows.map((r) => r.externalKey)).toEqual(["ENG-123", "ENG-124"]);
    rows.forEach((r) => expect(r.externalKey).toMatch(/^[A-Z]+-\d+$/));
    const eng123 = rows.find((r) => r.externalKey === "ENG-123")!;
    expect(JSON.parse(eng123.labels)).toEqual(["bug", "project:Q2 Launch", "cycle:7"]);
    const eng124 = rows.find((r) => r.externalKey === "ENG-124")!;
    expect(eng124.state).toBe("closed"); // type "completed" → closed
  });
});

describe("linear token refresh: a 401 from GraphQL triggers refresh + retry", () => {
  it("refreshes the access token once and retries, persisting the new pair", async () => {
    await db.integration.create({
      data: { orgId, provider: "linear", accessToken: "stale_access", refreshToken: "lin_refresh_1" },
    });
    const project = await db.project.create({
      data: { orgId, name: "p", linearTeamId: "team_eng", linearTeamKey: "ENG", createdById: userId },
    });

    let graphqlCalls = 0;
    let refreshCalled = false;
    globalThis.fetch = (async (url: string, init: RequestInit) => {
      const u = String(url);
      if (u.includes("/oauth/token")) {
        refreshCalled = true;
        return json({ access_token: "fresh_access", refresh_token: "fresh_refresh" });
      }
      // graphql
      graphqlCalls++;
      const auth = (init.headers as Record<string, string>).Authorization;
      if (graphqlCalls === 1) {
        expect(auth).toBe("stale_access");
        return new Response("{}", { status: 401 });
      }
      expect(auth).toBe("fresh_access"); // retry uses refreshed token
      return json(teamIssuesPayload([SAMPLE_NODES[0]]));
    }) as unknown as typeof fetch;

    const res = await request(app)
      .post(`/api/orgs/${orgId}/projects/${project.id}/sync`)
      .set("X-User-Id", "linacme-founder");
    expect(res.status).toBe(200);
    expect(refreshCalled).toBe(true);
    expect(graphqlCalls).toBe(2); // 401 then success — single retry, no loop
    const row = await db.integration.findUnique({
      where: { orgId_provider: { orgId, provider: "linear" } },
    });
    expect(row!.accessToken).toBe("fresh_access");
    expect(row!.refreshToken).toBe("fresh_refresh");
  });
});
