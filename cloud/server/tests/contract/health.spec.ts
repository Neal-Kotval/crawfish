import { describe, it, expect } from "vitest";
import { client } from "./setup.js";

describe("GET /api/health", () => {
  it("returns 200 ok:true", async () => {
    const res = await client().get("/api/health");
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ ok: true });
  });
});
