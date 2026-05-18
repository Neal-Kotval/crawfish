import { describe, it, expect } from "vitest";
import { client, asUser } from "./setup.js";

const ALPHA_PROJECT =
  "Alpha is a long-form project description used to satisfy the >40 char hint.";

describe("POST /api/orgs", () => {
  it("creates an org with default agents and returns 201", async () => {
    const res = await asUser(client().post("/api/orgs"), "alice").send({
      name: "alpha-org",
      project: ALPHA_PROJECT,
      primaryClient: "Dash",
      teamSize: "Just me",
    });

    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty("id");
    expect(res.body.name).toBe("alpha-org");
    expect(Array.isArray(res.body.agents)).toBe(true);
    expect(res.body.agents.length).toBe(4);
  });

  it("returns 409 name_taken when the org name is reused", async () => {
    const res = await asUser(client().post("/api/orgs"), "alice").send({
      name: "alpha-org",
      project: ALPHA_PROJECT,
      primaryClient: "Dash",
      teamSize: "Just me",
    });
    expect(res.status).toBe(409);
    expect(res.body.error?.code).toBe("name_taken");
  });

  it("rejects an invalid name with 400 invalid_body", async () => {
    const res = await asUser(client().post("/api/orgs"), "alice").send({
      name: "Bad Name",
      project: ALPHA_PROJECT,
      primaryClient: "Dash",
      teamSize: "Just me",
    });
    expect(res.status).toBe(400);
    expect(res.body.error?.code).toBe("invalid_body");
    expect(res.body.error?.message ?? "").toMatch(/lowercase/);
  });

  it("rejects an invalid teamSize with a 400 Zod error", async () => {
    const res = await asUser(client().post("/api/orgs"), "alice").send({
      name: "another-org",
      project: ALPHA_PROJECT,
      primaryClient: "Dash",
      teamSize: "solo",
    });
    expect(res.status).toBe(400);
    expect(res.body.error?.code).toBe("invalid_body");
    expect(res.body.error?.message ?? "").toMatch(/teamSize/);
  });
});

describe("GET /api/me/orgs and /api/orgs/:id", () => {
  it("lists the creator's orgs with counts", async () => {
    const res = await asUser(client().get("/api/me/orgs"), "alice");
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    const alpha = res.body.find((o: { name: string }) => o.name === "alpha-org");
    expect(alpha).toBeDefined();
    expect(alpha.memberCount).toBe(1);
    expect(alpha.agentCount).toBe(4);
    expect(alpha.role).toBe("founder");
  });

  it("returns the full org by cuid for the creator", async () => {
    const list = await asUser(client().get("/api/me/orgs"), "alice");
    const alpha = list.body.find((o: { name: string }) => o.name === "alpha-org");
    const res = await asUser(client().get(`/api/orgs/${alpha.id}`), "alice");
    expect(res.status).toBe(200);
    expect(res.body.id).toBe(alpha.id);
    expect(Array.isArray(res.body.members)).toBe(true);
    expect(Array.isArray(res.body.agents)).toBe(true);
  });

  it("also resolves by slug (org.name)", async () => {
    const res = await asUser(client().get("/api/orgs/alpha-org"), "alice");
    expect(res.status).toBe(200);
    expect(res.body.name).toBe("alpha-org");
  });

  it("returns 403 to a non-member", async () => {
    const res = await asUser(client().get("/api/orgs/alpha-org"), "mallory");
    expect(res.status).toBe(403);
    expect(res.body.error?.code).toBe("forbidden");
  });

  it("returns 404 for a non-existent org", async () => {
    const res = await asUser(client().get("/api/orgs/no-such-org"), "alice");
    expect(res.status).toBe(404);
    expect(res.body.error?.code).toBe("not_found");
  });
});
