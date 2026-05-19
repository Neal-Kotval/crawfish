import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  CRITERIA_TOOL_DEFS,
  dispatchCriteria,
  dispatchCriteriaSet,
  dispatchCriteriaAttest,
} from "../src/criteria.js";

// ---------- Tool definition shape ----------

describe("CRITERIA_TOOL_DEFS", () => {
  it("exposes criteria_set and criteria_attest", () => {
    assert.equal(CRITERIA_TOOL_DEFS.length, 2);
    const names = CRITERIA_TOOL_DEFS.map((t) => t.name).sort();
    assert.deepEqual(names, ["criteria_attest", "criteria_set"]);
  });

  it("descriptions are substantial (context-injection text)", () => {
    for (const t of CRITERIA_TOOL_DEFS) {
      assert.ok(
        (t.description?.length ?? 0) > 80,
        `description for ${t.name} too short`,
      );
    }
  });

  it("criteria_set requires org_id, task_id, by, criteria", () => {
    const t = CRITERIA_TOOL_DEFS.find((x) => x.name === "criteria_set")!;
    const schema = t.inputSchema as Record<string, unknown>;
    assert.deepEqual(
      (schema.required as string[]).slice().sort(),
      ["by", "criteria", "org_id", "task_id"],
    );
  });

  it("criteria_attest requires org_id, task_id, criterion_id, by, evidence", () => {
    const t = CRITERIA_TOOL_DEFS.find((x) => x.name === "criteria_attest")!;
    const schema = t.inputSchema as Record<string, unknown>;
    assert.deepEqual(
      (schema.required as string[]).slice().sort(),
      ["by", "criterion_id", "evidence", "org_id", "task_id"],
    );
  });
});

// ---------- dispatchCriteriaSet — happy path ----------

describe("dispatchCriteriaSet happy path", () => {
  it("PATCHes /api/orgs/:id/board/tasks/:tid/criteria and returns ok", async () => {
    let captured: any = null;
    const fetchStub = async (url: string, init: RequestInit) => {
      captured = { url: String(url), init };
      return {
        ok: true,
        status: 200,
        json: async () => ({ ok: true }),
      } as Response;
    };

    const result = await dispatchCriteriaSet(
      {
        org_id: "o1",
        task_id: "t1",
        by: "founder",
        criteria: [
          { id: "c1", statement: "Returns 200 on read", kind: "test" },
          {
            id: "c2",
            statement: "p95 latency under 200ms",
            kind: "metric",
          },
        ],
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );

    assert.equal(result.tokens_used, 0);
    assert.ok("ok" in result && result.ok === true);
    assert.ok(captured);
    assert.ok(captured!.url.endsWith("/api/orgs/o1/board/tasks/t1/criteria"));
    assert.equal(captured!.init.method, "PATCH");
    const body = JSON.parse(captured!.init.body as string);
    assert.equal(body.by, "founder");
    assert.equal(body.criteria.length, 2);
  });
});

describe("dispatchCriteriaAttest happy path", () => {
  it("PATCHes /api/orgs/:id/board/tasks/:tid/criteria/:cid and returns ok", async () => {
    let captured: any = null;
    const fetchStub = async (url: string, init: RequestInit) => {
      captured = { url: String(url), init };
      return {
        ok: true,
        status: 200,
        json: async () => ({ ok: true }),
      } as Response;
    };

    const result = await dispatchCriteriaAttest(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c1",
        by: "founder",
        evidence: {
          kind: "test",
          payload: { path: "test/foo.test.ts", case: "happy path" },
        },
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );

    assert.equal(result.tokens_used, 0);
    assert.ok("ok" in result && result.ok === true);
    assert.ok(captured);
    assert.ok(captured!.url.endsWith("/api/orgs/o1/board/tasks/t1/criteria/c1"));
    assert.equal(captured!.init.method, "PATCH");
    const body = JSON.parse(captured!.init.body as string);
    assert.equal(body.by, "founder");
    assert.equal(body.evidence.kind, "test");
  });
});

// ---------- Error envelope ----------

describe("dispatchCriteria error envelope", () => {
  it("surfaces upstream 409 criteria_unmet", async () => {
    const fetchStub = async () =>
      ({
        ok: false,
        status: 409,
        json: async () => ({
          error: { code: "criteria_unmet", message: "unmet: [c2]" },
        }),
      } as Response);

    const result = await dispatchCriteriaAttest(
      {
        org_id: "o1",
        task_id: "t1",
        criterion_id: "c1",
        by: "founder",
        evidence: { kind: "test", payload: { path: "x" } },
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.ok("error" in result);
    assert.equal((result as any).error.code, "criteria_unmet");
  });

  it("surfaces upstream 404 not_found", async () => {
    const fetchStub = async () =>
      ({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({
          error: { code: "not_found", message: "task t99 not found" },
        }),
      } as Response);

    const result = await dispatchCriteriaSet(
      {
        org_id: "o1",
        task_id: "t99",
        by: "founder",
        criteria: [{ id: "c1", statement: "Some criterion statement", kind: "test" }],
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.ok("error" in result);
    assert.equal((result as any).error.code, "not_found");
  });

  it("falls back to upstream_error when body lacks an error envelope", async () => {
    const fetchStub = async () =>
      ({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({}),
      } as Response);

    const result = await dispatchCriteriaSet(
      {
        org_id: "o1",
        task_id: "t1",
        by: "founder",
        criteria: [{ id: "c1", statement: "Some criterion statement", kind: "test" }],
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.ok("error" in result);
    assert.equal((result as any).error.code, "upstream_error");
  });

  it("returns internal error envelope on network failure", async () => {
    const fetchStub = async () => {
      throw new Error("ECONNREFUSED");
    };
    const result = await dispatchCriteriaSet(
      {
        org_id: "o1",
        task_id: "t1",
        by: "founder",
        criteria: [{ id: "c1", statement: "Some criterion statement", kind: "test" }],
      },
      { fetch: fetchStub as typeof fetch },
    );
    assert.equal((result as any).error.code, "internal");
  });
});

// ---------- Input validation (client-side guards) ----------

describe("dispatchCriteriaSet input validation", () => {
  const fetchStub = async () =>
    ({ ok: true, status: 200, json: async () => ({ ok: true }) } as Response);

  it("rejects statement shorter than 8 chars", async () => {
    const result = await dispatchCriteriaSet(
      {
        org_id: "o1",
        task_id: "t1",
        by: "founder",
        criteria: [{ id: "c1", statement: "short", kind: "test" }],
      },
      { fetch: fetchStub as typeof fetch },
    );
    assert.equal((result as any).error.code, "invalid_argument");
    assert.match((result as any).error.message, /statement/);
  });

  it("rejects evidence kind mismatch with criterion kind", async () => {
    const result = await dispatchCriteriaSet(
      {
        org_id: "o1",
        task_id: "t1",
        by: "founder",
        criteria: [
          {
            id: "c1",
            statement: "p95 latency under 200ms",
            kind: "metric",
            evidence: { kind: "test", payload: {} },
          },
        ],
      },
      { fetch: fetchStub as typeof fetch },
    );
    assert.equal((result as any).error.code, "invalid_argument");
    assert.match((result as any).error.message, /kind/);
  });

  it("rejects malformed criterion id", async () => {
    const result = await dispatchCriteriaSet(
      {
        org_id: "o1",
        task_id: "t1",
        by: "founder",
        criteria: [{ id: "BAD ID!", statement: "Some statement here", kind: "test" }],
      },
      { fetch: fetchStub as typeof fetch },
    );
    assert.equal((result as any).error.code, "invalid_argument");
    assert.match((result as any).error.message, /id/);
  });

  it("rejects duplicate criterion ids", async () => {
    const result = await dispatchCriteriaSet(
      {
        org_id: "o1",
        task_id: "t1",
        by: "founder",
        criteria: [
          { id: "c1", statement: "First statement here", kind: "test" },
          { id: "c1", statement: "Second statement here", kind: "test" },
        ],
      },
      { fetch: fetchStub as typeof fetch },
    );
    assert.equal((result as any).error.code, "invalid_argument");
    assert.match((result as any).error.message, /duplicate/);
  });
});

// ---------- dispatchCriteria router ----------

describe("dispatchCriteria router", () => {
  it("routes criteria_set", async () => {
    const fetchStub = async () =>
      ({ ok: true, status: 200, json: async () => ({ ok: true }) } as Response);
    const result = await dispatchCriteria(
      "criteria_set",
      {
        org_id: "o1",
        task_id: "t1",
        by: "founder",
        criteria: [{ id: "c1", statement: "Some statement here", kind: "test" }],
      },
      { fetch: fetchStub as typeof fetch },
    );
    assert.ok("ok" in result);
  });

  it("returns unknown_tool for unrecognised names", async () => {
    const result = await dispatchCriteria("not_a_tool", {});
    assert.equal((result as any).error.code, "unknown_tool");
  });
});
