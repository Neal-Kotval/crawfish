import { describe, it, expect, beforeEach, afterAll } from "vitest";
import request from "supertest";
import { app, db } from "../../src/index.js";
import { _setClerkClientForTests } from "../../src/lib/github.js";
import { signOrgToken } from "../../src/lib/jwt.js";

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

function getAsFounder(path: string) {
  return request(app).get(path).set("X-User-Id", "acme-founder");
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

describe("GET /api/orgs/:orgId/projects", () => {
  it("lists projects for org members, newest first", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    await db.project.create({
      data: {
        orgId,
        name: "p1",
        cloneStatus: "pending",
        createdById: founder!.id,
        createdAt: new Date("2026-05-01T00:00:00Z"),
      },
    });
    await db.project.create({
      data: {
        orgId,
        name: "p2",
        cloneStatus: "local_only",
        createdById: founder!.id,
        createdAt: new Date("2026-05-02T00:00:00Z"),
      },
    });
    const res = await getAsFounder(`/api/orgs/${orgId}/projects`);
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(2);
    expect(res.body[0].name).toBe("p2");
    expect(res.body[1].name).toBe("p1");
  });

  it("returns empty list when org has no projects", async () => {
    const res = await getAsFounder(`/api/orgs/${orgId}/projects`);
    expect(res.status).toBe(200);
    expect(res.body).toEqual([]);
  });

  it("rejects non-members with 404", async () => {
    const res = await request(app)
      .get(`/api/orgs/${orgId}/projects`)
      .set("X-User-Id", "outsider");
    expect(res.status).toBe(404);
  });
});

describe("PATCH /api/orgs/:orgId/projects/:pid", () => {
  it("allows founder to rename a project via web auth", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: { orgId, name: "old-name", cloneStatus: "pending", createdById: founder!.id },
    });
    const res = await request(app)
      .patch(`/api/orgs/${orgId}/projects/${p.id}`)
      .set("X-User-Id", "acme-founder")
      .send({ name: "new-name" });
    expect(res.status).toBe(200);
    expect(res.body.name).toBe("new-name");
  });

  it("rejects clone-field updates via web auth with 403", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: { orgId, name: "p1", cloneStatus: "pending", createdById: founder!.id },
    });
    const res = await request(app)
      .patch(`/api/orgs/${orgId}/projects/${p.id}`)
      .set("X-User-Id", "acme-founder")
      .send({ cloneStatus: "cloned", localPath: "/x/y" });
    expect(res.status).toBe(403);
    expect(res.body.error.code).toBe("device_token_required");
  });

  it("updates clone fields when called via device-link JWT on /api/dash", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: { orgId, name: "p1", cloneStatus: "pending", createdById: founder!.id },
    });
    const token = signOrgToken(founder!.id, orgId);
    const res = await request(app)
      .patch(`/api/dash/orgs/${orgId}/projects/${p.id}`)
      .set("X-Crawfish-Token", token)
      .send({
        cloneStatus: "cloned",
        localPath: "/Users/me/crawfish/acme/p1",
        deviceId: "dev_xyz",
      });
    expect(res.status).toBe(200);
    expect(res.body.cloneStatus).toBe("cloned");
    expect(res.body.localPath).toBe("/Users/me/crawfish/acme/p1");
    expect(res.body.deviceId).toBe("dev_xyz");
  });

  it("returns 404 when project does not belong to the org", async () => {
    const res = await request(app)
      .patch(`/api/orgs/${orgId}/projects/nonexistent`)
      .set("X-User-Id", "acme-founder")
      .send({ name: "new-name" });
    expect(res.status).toBe(404);
  });
});

describe("DELETE /api/orgs/:orgId/projects/:pid", () => {
  it("removes the project bookmark for an org member", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: { orgId, name: "p1", cloneStatus: "pending", createdById: founder!.id },
    });
    const res = await request(app)
      .delete(`/api/orgs/${orgId}/projects/${p.id}`)
      .set("X-User-Id", "acme-founder");
    expect(res.status).toBe(204);
    const after = await db.project.findUnique({ where: { id: p.id } });
    expect(after).toBeNull();
  });

  it("rejects non-members with 404", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: { orgId, name: "p1", cloneStatus: "pending", createdById: founder!.id },
    });
    const res = await request(app)
      .delete(`/api/orgs/${orgId}/projects/${p.id}`)
      .set("X-User-Id", "outsider");
    expect(res.status).toBe(404);
    const after = await db.project.findUnique({ where: { id: p.id } });
    expect(after).not.toBeNull();
  });

  it("returns 404 when project does not belong to the org", async () => {
    const res = await request(app)
      .delete(`/api/orgs/${orgId}/projects/nonexistent`)
      .set("X-User-Id", "acme-founder");
    expect(res.status).toBe(404);
  });

});

describe("GET /api/orgs/:orgId/projects/:pid/files/:filename", () => {
  const repoMetaFetch = globalThis.fetch;

  function setFetch(fn: typeof fetch) {
    globalThis.fetch = fn;
  }
  function restoreFetch() {
    globalThis.fetch = repoMetaFetch;
  }

  it("returns 200 with markdown body when project is cloned and GH returns file", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: {
        orgId,
        name: "p1",
        cloneStatus: "cloned",
        githubRepo: "octo/hello",
        githubRepoId: 12345,
        defaultBranch: "main",
        createdById: founder!.id,
      },
    });
    setFetch((async () =>
      new Response("# Memory\n\nhello", {
        status: 200,
        headers: { "content-type": "text/plain" },
      })) as typeof fetch);
    try {
      const res = await getAsFounder(`/api/orgs/${orgId}/projects/${p.id}/files/memory.md`);
      expect(res.status).toBe(200);
      expect(res.headers["content-type"]).toMatch(/text\/markdown/);
      expect(res.text).toBe("# Memory\n\nhello");
    } finally {
      restoreFetch();
    }
  });

  it("rejects non-members with 404", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: {
        orgId,
        name: "p1",
        cloneStatus: "cloned",
        githubRepo: "octo/hello",
        githubRepoId: 12345,
        defaultBranch: "main",
        createdById: founder!.id,
      },
    });
    const res = await request(app)
      .get(`/api/orgs/${orgId}/projects/${p.id}/files/memory.md`)
      .set("X-User-Id", "outsider");
    expect(res.status).toBe(404);
  });

  it("rejects invalid filename with 400", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: {
        orgId,
        name: "p1",
        cloneStatus: "cloned",
        githubRepo: "octo/hello",
        githubRepoId: 12345,
        defaultBranch: "main",
        createdById: founder!.id,
      },
    });
    const res = await getAsFounder(`/api/orgs/${orgId}/projects/${p.id}/files/secrets.env`);
    expect(res.status).toBe(400);
    expect(res.body.error.code).toBe("invalid_filename");
  });

  it("returns 404 file_not_found when GitHub returns 404", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: {
        orgId,
        name: "p1",
        cloneStatus: "cloned",
        githubRepo: "octo/hello",
        githubRepoId: 12345,
        defaultBranch: "main",
        createdById: founder!.id,
      },
    });
    setFetch((async () =>
      new Response("Not Found", { status: 404 })) as typeof fetch);
    try {
      const res = await getAsFounder(`/api/orgs/${orgId}/projects/${p.id}/files/memory.md`);
      expect(res.status).toBe(404);
      expect(res.body.error.code).toBe("file_not_found");
    } finally {
      restoreFetch();
    }
  });

  it("returns 409 project_not_initialized when project is pending", async () => {
    const founder = await db.user.findUnique({ where: { email: "acme-founder@local" } });
    const p = await db.project.create({
      data: {
        orgId,
        name: "p1",
        cloneStatus: "pending",
        githubRepo: "octo/hello",
        githubRepoId: 12345,
        defaultBranch: "main",
        createdById: founder!.id,
      },
    });
    const res = await getAsFounder(`/api/orgs/${orgId}/projects/${p.id}/files/memory.md`);
    expect(res.status).toBe(409);
    expect(res.body.error.code).toBe("project_not_initialized");
  });
});
