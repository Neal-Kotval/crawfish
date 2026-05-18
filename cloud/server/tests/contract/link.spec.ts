/**
 * Device-link contract tests.
 *
 * Note: the ROADMAP description references `/api/orgs/:id/link` but the
 * server actually exposes `/api/device-link` (Dash posts the org payload in
 * the body anonymously — see src/routes/deviceLink.ts). The tests below
 * cover the routes that exist; if the URL surface ever moves, the assertions
 * should follow.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { client, asUser, db } from "./setup.js";

let code = "";
let orgId = "";

describe("device-link", () => {
  beforeAll(async () => {
    const res = await client().post("/api/device-link").send({
      localOrg: {
        name: "link-org",
        project: "Device-link project description used in the link contract suite.",
        teamSize: "Just me",
        primaryClient: "Dash",
        agents: [
          { name: "eng-bot", role: "engineer", runtime: "claude-code" },
        ],
      },
    });
    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty("code");
    expect(res.body).toHaveProperty("verifyUrl");
    code = res.body.code;

    const row = await db.deviceLinkCode.findUnique({ where: { code } });
    orgId = row!.orgId;
  });

  it("pre-redeem GET returns pending:true", async () => {
    const res = await client().get(`/api/device-link/${code}`);
    expect(res.status).toBe(200);
    expect(res.body.pending).toBe(true);
  });

  it("user B redeems the code and the response carries server-vouched user info", async () => {
    const res = await asUser(
      client().post(`/api/device-link/${code}/redeem`),
      "linker-b",
      "linker-b@example.com",
    );
    expect(res.status).toBe(200);
    expect(res.body.org?.id).toBe(orgId);
    expect(res.body.org?.name).toBe("link-org");
    expect(res.body.user?.email).toBe("linker-b@example.com");
    expect(typeof res.body.user?.name).toBe("string");
  });

  it("post-redeem GET returns the auth token + org + user and is single-use", async () => {
    const res = await client().get(`/api/device-link/${code}`);
    expect(res.status).toBe(200);
    expect(res.body.redeemedAt).toBeTruthy();
    expect(res.body.authToken).toBeTruthy();
    expect(res.body.org?.name).toBe("link-org");
    expect(res.body.user?.email).toBe("linker-b@example.com");

    // Single-use: row is deleted after read.
    const after = await client().get(`/api/device-link/${code}`);
    expect(after.status).toBe(404);
  });

  it("expired code returns 410", async () => {
    const created = await client().post("/api/device-link").send({
      localOrg: { name: "link-org-expired", agents: [] },
    });
    expect(created.status).toBe(201);
    const expiredCode = created.body.code;

    await db.deviceLinkCode.update({
      where: { code: expiredCode },
      data: { expiresAt: new Date(Date.now() - 60_000) },
    });

    const res = await client().get(`/api/device-link/${expiredCode}`);
    expect(res.status).toBe(410);
  });

  it("unknown code returns 404", async () => {
    const res = await client().get("/api/device-link/ZZZZZZ");
    expect(res.status).toBe(404);
  });
});
