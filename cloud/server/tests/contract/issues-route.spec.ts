import { describe, it, expect, beforeEach } from "vitest";
import request from "supertest";
import { app, db } from "../../src/index.js";

// Exercises the list/sync route RBAC without touching any provider — issues
// are seeded directly so no fetch/Clerk stub is needed.

let orgId: string;
let projectId: string;

beforeEach(async () => {
  await db.issue.deleteMany({});
  await db.project.deleteMany({});
  await db.orgMember.deleteMany({});
  await db.org.deleteMany({ where: { name: "issroute" } });

  const founder = await db.user.upsert({
    where: { email: "issroute-founder@local" },
    update: {},
    create: { email: "issroute-founder@local", name: "issroute-founder" },
  });
  const org = await db.org.create({ data: { name: "issroute" } });
  orgId = org.id;
  await db.orgMember.create({ data: { orgId, userId: founder.id, role: "founder" } });

  const project = await db.project.create({
    data: { orgId, name: "p1", githubRepo: "octo/p1", createdById: founder.id },
  });
  projectId = project.id;
  await db.issue.create({
    data: {
      projectId,
      provider: "github",
      externalId: "I_seed1",
      externalKey: "#1",
      number: 1,
      title: "Seeded issue",
      state: "open",
      labels: JSON.stringify(["seed"]),
      syncedAt: new Date(),
    },
  });

  // A second project in the SAME org, with its own issue — proves the list
  // route scopes by project, not just by org.
  const other = await db.project.create({
    data: { orgId, name: "p2", githubRepo: "octo/p2", createdById: founder.id },
  });
  await db.issue.create({
    data: {
      projectId: other.id,
      provider: "github",
      externalId: "I_seed2",
      externalKey: "#9",
      number: 9,
      title: "Other project issue",
      state: "open",
      labels: "[]",
      syncedAt: new Date(),
    },
  });
});

describe("GET …/issues returns only that project's issues to a member", () => {
  it("scopes by project and parses labels into an array", async () => {
    const res = await request(app)
      .get(`/api/orgs/${orgId}/projects/${projectId}/issues`)
      .set("X-User-Id", "issroute-founder");
    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0]).toMatchObject({ externalKey: "#1", title: "Seeded issue" });
    expect(res.body[0].labels).toEqual(["seed"]);
  });
});

describe("non-member gets 404 on GET …/issues and POST …/sync", () => {
  it("rejects an outsider on the list route", async () => {
    const res = await request(app)
      .get(`/api/orgs/${orgId}/projects/${projectId}/issues`)
      .set("X-User-Id", "issroute-outsider");
    expect(res.status).toBe(404);
  });

  it("rejects an outsider on the sync route", async () => {
    const res = await request(app)
      .post(`/api/orgs/${orgId}/projects/${projectId}/sync`)
      .set("X-User-Id", "issroute-outsider");
    expect(res.status).toBe(404);
  });

  it("rejects an outsider on GET …/integrations", async () => {
    const res = await request(app)
      .get(`/api/orgs/${orgId}/integrations`)
      .set("X-User-Id", "issroute-outsider");
    expect(res.status).toBe(404);
  });
});
