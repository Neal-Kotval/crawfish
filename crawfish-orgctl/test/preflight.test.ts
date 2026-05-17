import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { PREFLIGHT_TOOL_DEFS, dispatchPreflight } from "../src/preflight.js";

// ---------- Tool definition shape ----------

describe("PREFLIGHT_TOOL_DEFS", () => {
  it("exposes a single preflight_attest tool", () => {
    assert.equal(PREFLIGHT_TOOL_DEFS.length, 1);
    assert.equal(PREFLIGHT_TOOL_DEFS[0].name, "preflight_attest");
    assert.ok(
      (PREFLIGHT_TOOL_DEFS[0].description?.length ?? 0) > 50,
      "description must be substantial (context-injection text)",
    );
  });

  it("inputSchema requires org_id, task_id, criterion_id, by, statement", () => {
    const schema = PREFLIGHT_TOOL_DEFS[0].inputSchema as Record<string, unknown>;
    assert.deepEqual(
      (schema.required as string[]).sort(),
      ["by", "criterion_id", "org_id", "statement", "task_id"],
    );
  });

  it("inputSchema lists payload as optional (not in required)", () => {
    const schema = PREFLIGHT_TOOL_DEFS[0].inputSchema as Record<string, unknown>;
    const required = schema.required as string[];
    assert.ok(!required.includes("payload"), "payload must be optional");
    const props = schema.properties as Record<string, unknown>;
    assert.ok("payload" in props, "payload must be listed in properties");
  });
});

// ---------- dispatchPreflight — happy path ----------

describe("dispatchPreflight happy path", () => {
  it("forwards to POST /api/orgs/:id/preflight and returns event_id", async () => {
    const fetchStub = async (url: string, init: RequestInit) => {
      assert.ok(String(url).includes("/api/orgs/o1/preflight"));
      assert.equal(init.method, "POST");
      const body = JSON.parse(init.body as string);
      assert.equal(body.task_id, "t1");
      assert.equal(body.criterion_id, "c1");
      assert.equal(body.by, "founder");
      assert.equal(body.statement, "Read the spec §3.3 in full");
      return {
        ok: true,
        status: 200,
        json: async () => ({ event_id: "EV01" }),
      } as Response;
    };

    const result = await dispatchPreflight(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c1",
        by: "founder",
        statement: "Read the spec §3.3 in full",
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.equal((result as any).event_id, "EV01");
    assert.ok(!("error" in result), "no error on success");
  });

  it("forwards optional payload field when provided", async () => {
    let capturedBody: any;
    const fetchStub = async (_url: string, init: RequestInit) => {
      capturedBody = JSON.parse(init.body as string);
      return {
        ok: true,
        status: 200,
        json: async () => ({ event_id: "EV02" }),
      } as Response;
    };

    await dispatchPreflight(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c1",
        by: "founder",
        statement: "Verified fixture at test/fixtures/foo",
        payload: { kind: "preflight", sources: ["docs/spec.md"] },
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.deepEqual(capturedBody.payload, { kind: "preflight", sources: ["docs/spec.md"] });
  });
});

// ---------- dispatchPreflight — error paths ----------

describe("dispatchPreflight error paths", () => {
  it("returns error envelope on 404 unknown_criterion", async () => {
    const fetchStub = async () => ({
      ok: false,
      status: 404,
      json: async () => ({ error: { code: "unknown_criterion", message: "criterion c99 not found" } }),
    } as Response);

    const result = await dispatchPreflight(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c99",
        by: "founder",
        statement: "Read the spec in full detail",
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.ok("error" in result);
    assert.equal((result as any).error.code, "unknown_criterion");
  });

  it("returns error envelope on 400 invalid_statement", async () => {
    const fetchStub = async () => ({
      ok: false,
      status: 400,
      json: async () => ({ error: { code: "invalid_statement", message: "statement too short" } }),
    } as Response);

    const result = await dispatchPreflight(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c1",
        by: "founder",
        statement: "too short",
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.equal((result as any).error.code, "invalid_statement");
  });

  it("returns error envelope on network failure", async () => {
    const fetchStub = async () => {
      throw new Error("ECONNREFUSED");
    };

    const result = await dispatchPreflight(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c1",
        by: "founder",
        statement: "Read the entire specification carefully",
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.ok("error" in result);
    assert.equal((result as any).error.code, "internal");
    assert.ok((result as any).error.message.includes("ECONNREFUSED"));
  });

  it("does NOT retry on 409", async () => {
    let callCount = 0;
    const fetchStub = async () => {
      callCount++;
      return {
        ok: false,
        status: 409,
        json: async () => ({ error: { code: "criteria_unmet", message: "unmet" } }),
      } as Response;
    };

    const result = await dispatchPreflight(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c1",
        by: "founder",
        statement: "Checked all prerequisites thoroughly",
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(callCount, 1, "must not retry on 409");
    assert.equal(result.tokens_used, 0);
    assert.equal((result as any).error.code, "criteria_unmet");
  });
});

// ---------- tokens_used is always 0 ----------

describe("tokens_used contract", () => {
  it("is always 0 (attestation is metadata, not an LLM call)", async () => {
    const fetchStub = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ event_id: "EV03" }),
    } as Response);

    const result = await dispatchPreflight(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c1",
        by: "founder",
        statement: "Thoroughly reviewed the implementation plan",
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
  });
});
