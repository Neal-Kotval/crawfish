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

// Stub global fetch so fetchRepoMetadata returns canned repo metadata.
const realFetch = globalThis.fetch;
globalThis.fetch = (async () =>
  new Response(
    JSON.stringify({
      id: 12345,
      full_name: "octo/hello",
      default_branch: "main",
      private: false,
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  )) as typeof fetch;

afterAll(() => {
  _setClerkClientForTests(null);
  globalThis.fetch = realFetch;
});

let orgId: string;

beforeEach(async () => {
  // Clean projects + memberships + orgs for the founder so each test starts fresh.
  await db.project.deleteMany({});
  await db.orgMember.deleteMany({});
  await db.org.deleteMany({ where: { name: "acme" } });

  const founderEmail = "acme-founder@local";
  const founder = await db.user.upsert({
    where: { email: founderEmail },
    update: {},
    create: { email: founderEmail, name: "acme-founder" },
  });
  const org = await db.org.create({ data: { name: "acme" } });
  orgId = org.id;
  await db.orgMember.create({ data: { orgId, userId: founder.id, role: "founder" } });
});

function postAsFounder(path: string) {
  return request(app).post(path).set("X-User-Id", "acme-founder");
}

describe("POST /api/orgs/:orgId/projects (clone path)", () => {
  it("creates a project in pending status", async () => {
    const res = await postAsFounder(`/api/orgs/${orgId}/projects`).send({ githubRepoId: 12345 });
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({
      githubRepo: "octo/hello",
      cloneStatus: "pending",
      defaultBranch: "main",
    });
  });

  it("is idempotent on (orgId, githubRepoId)", async () => {
    await postAsFounder(`/api/orgs/${orgId}/projects`).send({ githubRepoId: 12345 });
    const res = await postAsFounder(`/api/orgs/${orgId}/projects`).send({ githubRepoId: 12345 });
    expect(res.status).toBe(200);
    expect(await db.project.count({ where: { orgId } })).toBe(1);
  });

  it("rejects non-members with 404", async () => {
    const res = await request(app)
      .post(`/api/orgs/${orgId}/projects`)
      .set("X-User-Id", "outsider")
      .send({ githubRepoId: 12345 });
    expect(res.status).toBe(404);
  });
});

describe("POST /api/orgs/:orgId/projects (adopt-local path)", () => {
  it("creates local_only when no githubRepoId", async () => {
    const res = await postAsFounder(`/api/orgs/${orgId}/projects`).send({
      name: "myrepo",
      localPath: "/Users/me/code/myrepo",
      deviceId: "dev_abc",
    });
    expect(res.status).toBe(201);
    expect(res.body.cloneStatus).toBe("local_only");
    expect(res.body.localPath).toBe("/Users/me/code/myrepo");
    expect(res.body.name).toBe("myrepo");
    expect(res.body.githubRepo).toBeNull();
  });

  it("creates cloned when githubRepoId is provided and accessible", async () => {
    const res = await postAsFounder(`/api/orgs/${orgId}/projects`).send({
      name: "myrepo",
      localPath: "/Users/me/code/myrepo",
      deviceId: "dev_abc",
      githubRepoId: 12345,
    });
    expect(res.status).toBe(201);
    expect(res.body.cloneStatus).toBe("cloned");
    expect(res.body.githubRepo).toBe("octo/hello");
    expect(res.body.localPath).toBe("/Users/me/code/myrepo");
  });
});
