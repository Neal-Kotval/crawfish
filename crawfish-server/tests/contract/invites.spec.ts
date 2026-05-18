import { describe, it, expect, beforeAll } from "vitest";
import { client, asUser, db } from "./setup.js";

const PROJECT =
  "An invites-suite project description that comfortably exceeds the 40 character soft hint.";

let orgId = "";

describe("invites", () => {
  beforeAll(async () => {
    // Create an org owned by user A. Each spec file shares the wiped DB but
    // we don't depend on orgs.spec.ts having run.
    const res = await asUser(client().post("/api/orgs"), "a-user", "a@example.com").send({
      name: "invites-org",
      project: PROJECT,
      primaryClient: "Dash",
      teamSize: "Just me",
    });
    expect(res.status).toBe(201);
    orgId = res.body.id;
  });

  it("user A creates an invite for b@example.com", async () => {
    const res = await asUser(
      client().post(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    ).send({ email: "b@example.com", role: "contributor" });

    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty("code");
    expect(res.body.mockEmail?.link).toMatch(/\/invites\//);
  });

  it("non-member B cannot create invites on A's org", async () => {
    const res = await asUser(
      client().post(`/api/orgs/${orgId}/invites`),
      "b-user",
      "b@example.com",
    ).send({ email: "c@example.com", role: "contributor" });
    expect(res.status).toBe(403);
    expect(res.body.error?.code).toBe("forbidden");
  });

  it("A lists pending invites and sees the code in dev mode", async () => {
    const res = await asUser(
      client().get(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    );
    expect(res.status).toBe(200);
    expect(res.body.length).toBeGreaterThanOrEqual(1);
    expect(res.body[0]).toHaveProperty("code");
  });

  it("public GET /api/invites/:code returns org name + email + expiresAt", async () => {
    const list = await asUser(
      client().get(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    );
    const invite = list.body.find((i: { email: string }) => i.email === "b@example.com");
    const res = await client().get(`/api/invites/${invite.code}`);
    expect(res.status).toBe(200);
    expect(res.body.org?.name).toBe("invites-org");
    expect(res.body.email).toBe("b@example.com");
    expect(res.body.expiresAt).toBeTruthy();
  });

  it("B accepts the invite (matching email) and becomes a member", async () => {
    const list = await asUser(
      client().get(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    );
    const invite = list.body.find((i: { email: string }) => i.email === "b@example.com");

    const accept = await asUser(
      client().post(`/api/invites/${invite.code}/accept`),
      "b-user",
      "b@example.com",
    );
    expect(accept.status).toBe(200);

    // B can now read the org.
    const orgView = await asUser(
      client().get(`/api/orgs/${orgId}`),
      "b-user",
      "b@example.com",
    );
    expect(orgView.status).toBe(200);
  });

  it("re-accepting the same invite returns 410 already_redeemed", async () => {
    // Find the now-redeemed invite directly.
    const invite = await db.invite.findFirst({
      where: { orgId, email: "b@example.com" },
    });
    expect(invite).toBeTruthy();
    const res = await asUser(
      client().post(`/api/invites/${invite!.code}/accept`),
      "b-user",
      "b@example.com",
    );
    expect(res.status).toBe(410);
  });

  it("expired invite: preview 410 and accept 410", async () => {
    // Create a fresh invite, then mutate expiresAt to the past.
    const created = await asUser(
      client().post(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    ).send({ email: "expired@example.com", role: "contributor" });
    expect(created.status).toBe(201);
    const code = created.body.code;

    await db.invite.update({
      where: { code },
      data: { expiresAt: new Date(Date.now() - 60_000) },
    });

    const preview = await client().get(`/api/invites/${code}`);
    expect(preview.status).toBe(410);

    const accept = await asUser(
      client().post(`/api/invites/${code}/accept`),
      "expired-user",
      "expired@example.com",
    );
    expect(accept.status).toBe(410);
  });

  it("EMAIL_MISMATCH: invite for c@, accept as d@ → 403", async () => {
    const created = await asUser(
      client().post(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    ).send({ email: "c@example.com", role: "contributor" });
    expect(created.status).toBe(201);
    const code = created.body.code;

    const res = await asUser(
      client().post(`/api/invites/${code}/accept`),
      "d-user",
      "d@example.com",
    );
    expect(res.status).toBe(403);
    expect(res.body.error?.code).toBe("EMAIL_MISMATCH");
  });

  it("email match is case-insensitive: CASE@EXAMPLE.COM ↔ case@example.com", async () => {
    const created = await asUser(
      client().post(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    ).send({ email: "CASE@EXAMPLE.COM", role: "contributor" });
    expect(created.status).toBe(201);
    const code = created.body.code;

    const res = await asUser(
      client().post(`/api/invites/${code}/accept`),
      "case-user",
      "case@example.com",
    );
    expect(res.status).toBe(200);
  });

  it("DELETE /api/orgs/:id/invites/:inviteId revokes a pending invite", async () => {
    const created = await asUser(
      client().post(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    ).send({ email: "revoke@example.com", role: "contributor" });
    expect(created.status).toBe(201);
    const inviteId = created.body.id;

    const del = await asUser(
      client().delete(`/api/orgs/${orgId}/invites/${inviteId}`),
      "a-user",
      "a@example.com",
    );
    expect(del.status).toBe(204);

    const list = await asUser(
      client().get(`/api/orgs/${orgId}/invites`),
      "a-user",
      "a@example.com",
    );
    expect(list.body.find((i: { id: string }) => i.id === inviteId)).toBeUndefined();
  });
});
