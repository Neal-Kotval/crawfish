import { describe, it, expect, beforeEach, afterAll } from "vitest";
import request from "supertest";
import { app, db } from "../../src/index.js";
import { _setClerkClientForTests } from "../../src/lib/github.js";

// Stub Clerk so getGithubToken returns a fake token without hitting the API.
_setClerkClientForTests({
  users: {
    getUserOauthAccessToken: async () => ({ data: [{ token: "gho_test" }] }),
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
} as any);

// Two real issues + one pull request (carries the `pull_request` key, must be
// excluded). Length < 100 so the sync paginator stops after page 1.
const ghPayload = [
  {
    node_id: "I_kwAA1",
    number: 1,
    title: "Bug A",
    body: "something broke",
    state: "open",
    html_url: "https://github.com/octo/hello/issues/1",
    labels: [{ name: "bug" }],
    assignee: { login: "alice" },
    updated_at: "2026-05-10T00:00:00Z",
  },
  {
    node_id: "I_kwAA2",
    number: 2,
    title: "Feature B",
    body: null,
    state: "closed",
    html_url: "https://github.com/octo/hello/issues/2",
    labels: ["enhancement"],
    assignee: null,
    updated_at: "2026-05-09T00:00:00Z",
  },
  {
    node_id: "PR_kwAA3",
    number: 3,
    title: "A pull request",
    body: null,
    state: "open",
    html_url: "https://github.com/octo/hello/pull/3",
    labels: [],
    assignee: null,
    updated_at: "2026-05-08T00:00:00Z",
    pull_request: { url: "https://api.github.com/repos/octo/hello/pulls/3" },
  },
];

const realFetch = globalThis.fetch;
globalThis.fetch = (async () =>
  new Response(JSON.stringify(ghPayload), {
    status: 200,
    headers: { "content-type": "application/json" },
  })) as typeof fetch;

afterAll(() => {
  _setClerkClientForTests(null);
  globalThis.fetch = realFetch;
});

let orgId: string;
let projectId: string;

beforeEach(async () => {
  await db.issue.deleteMany({});
  await db.project.deleteMany({});
  await db.orgMember.deleteMany({});
  await db.org.deleteMany({ where: { name: "ghissues" } });

  const founder = await db.user.upsert({
    where: { email: "ghissues-founder@local" },
    update: {},
    create: { email: "ghissues-founder@local", name: "ghissues-founder" },
  });
  const org = await db.org.create({ data: { name: "ghissues" } });
  orgId = org.id;
  await db.orgMember.create({ data: { orgId, userId: founder.id, role: "founder" } });
  const project = await db.project.create({
    data: {
      orgId,
      name: "hello",
      githubRepo: "octo/hello",
      githubRepoId: 12345,
      defaultBranch: "main",
      cloneStatus: "cloned",
      createdById: founder.id,
    },
  });
  projectId = project.id;
});

function asFounder(method: "get" | "post", path: string) {
  return request(app)[method](path).set("X-User-Id", "ghissues-founder");
}

describe("github sync upserts repo issues into Issue (OrgMember-gated)", () => {
  it("syncs repo issues and lists them, excluding pull requests", async () => {
    const sync = await asFounder("post", `/api/orgs/${orgId}/projects/${projectId}/sync`);
    expect(sync.status).toBe(200);
    expect(sync.body).toMatchObject({ provider: "github", synced: 2 });

    const list = await asFounder("get", `/api/orgs/${orgId}/projects/${projectId}/issues`);
    expect(list.status).toBe(200);
    expect(list.body).toHaveLength(2);
    const keys = list.body.map((i: { externalKey: string }) => i.externalKey).sort();
    expect(keys).toEqual(["#1", "#2"]);
    const bugA = list.body.find((i: { externalKey: string }) => i.externalKey === "#1");
    expect(bugA).toMatchObject({ title: "Bug A", state: "open", assigneeExternal: "alice" });
    expect(bugA.labels).toEqual(["bug"]);
  });

  it("excludes pull requests (items with pull_request key are not persisted)", async () => {
    await asFounder("post", `/api/orgs/${orgId}/projects/${projectId}/sync`);
    const prRow = await db.issue.findFirst({ where: { externalId: "PR_kwAA3" } });
    expect(prRow).toBeNull();
    expect(await db.issue.count({ where: { projectId } })).toBe(2);
  });

  it("idempotent re-sync: second sync leaves row count unchanged and advances syncedAt", async () => {
    await asFounder("post", `/api/orgs/${orgId}/projects/${projectId}/sync`);
    const first = await db.issue.findFirstOrThrow({ where: { externalId: "I_kwAA1" } });
    await new Promise((r) => setTimeout(r, 5));
    const second = await asFounder("post", `/api/orgs/${orgId}/projects/${projectId}/sync`);
    expect(second.body.synced).toBe(2);
    expect(await db.issue.count({ where: { projectId } })).toBe(2);
    const after = await db.issue.findFirstOrThrow({ where: { externalId: "I_kwAA1" } });
    expect(after.id).toBe(first.id); // upserted in place, not recreated
    expect(after.syncedAt.getTime()).toBeGreaterThanOrEqual(first.syncedAt.getTime());
  });

  it("returns 400 nothing_to_sync for a project with no provider binding", async () => {
    const founder = await db.user.findFirstOrThrow({ where: { email: "ghissues-founder@local" } });
    const bare = await db.project.create({
      data: { orgId, name: "bare", cloneStatus: "local_only", createdById: founder.id },
    });
    const res = await asFounder("post", `/api/orgs/${orgId}/projects/${bare.id}/sync`);
    expect(res.status).toBe(400);
    expect(res.body.error.code).toBe("nothing_to_sync");
  });
});
