import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  BUDGET_TOOL_DEFS,
  dispatchBudget,
  dispatchBudgetReport,
  onBudgetBreach,
  type BudgetTask,
} from "../src/budget.js";

// ---------- Fixtures ----------

function makeTask(overrides: Partial<BudgetTask> = {}): BudgetTask {
  return {
    id: "t1",
    assignee: "agent-alice",
    status: "in_progress",
    token_budget: 1000,
    token_spent: 0,
    ...overrides,
  };
}

const FIXED_TS = "2026-05-19T12:00:00.000Z";

// ---------- onBudgetBreach — pure ratio logic ----------

describe("onBudgetBreach ratio thresholds", () => {
  it("does NOT escalate at 80% of budget", () => {
    const task = makeTask();
    const out = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 80,
      budget_cents: 100,
      now: FIXED_TS,
    });
    assert.equal(out.breached, false);
  });

  it("does NOT escalate at 99.9% of budget", () => {
    const task = makeTask();
    const out = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 999,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    assert.equal(out.breached, false);
  });

  it("escalates at exactly 100% of budget", () => {
    const task = makeTask();
    const out = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 1000,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    assert.equal(out.breached, true);
  });

  it("escalates at 200% of budget", () => {
    const task = makeTask();
    const out = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 2000,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    assert.equal(out.breached, true);
    if (out.breached) {
      assert.equal(out.event.payload.ratio, 2);
    }
  });
});

// ---------- Event + patch shape ----------

describe("onBudgetBreach event + patch shape", () => {
  it("emits a budget_breach event with the right payload", () => {
    const task = makeTask({ assignee: "agent-alice" });
    const out = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 1500,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    assert.equal(out.breached, true);
    if (!out.breached) return;

    assert.equal(out.event.type, "budget_breach");
    assert.equal(out.event.task_id, "t1");
    assert.equal(out.event.ts, FIXED_TS);
    assert.equal(out.event.payload.spent_cents, 1500);
    assert.equal(out.event.payload.budget_cents, 1000);
    assert.equal(out.event.payload.ratio, 1.5);
    assert.equal(out.event.payload.scope, "task");
    assert.deepEqual(out.event.payload.notify, { to: "agent-alice" });
  });

  it("patch sets status=escalated and stamps escalated_at + reason", () => {
    const task = makeTask();
    const out = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 1000,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    if (!out.breached) {
      assert.fail("expected breach");
    }
    assert.equal(out.patch.status, "escalated");
    assert.equal(out.patch.escalated_at, FIXED_TS);
    assert.equal(out.patch.escalated_reason, "budget_breach");
    assert.ok(out.patch.activity_log_append);
    assert.equal(out.patch.activity_log_append!.length, 1);
    assert.equal(out.patch.activity_log_append![0].kind, "budget_breach");
  });

  it("notify.to is null when task has no assignee", () => {
    const task = makeTask({ assignee: null });
    const out = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 1000,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    if (!out.breached) {
      assert.fail("expected breach");
    }
    assert.deepEqual(out.event.payload.notify, { to: null });
  });
});

// ---------- Dedupe + uncapped + invalid inputs ----------

describe("onBudgetBreach guards", () => {
  it("does NOT re-emit when task is already escalated (dedupe)", () => {
    const task = makeTask({ status: "escalated" });
    const out = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 5000,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    assert.equal(out.breached, false);
  });

  it("treats budget_cents <= 0 as uncapped (never breaches)", () => {
    const task = makeTask({ token_budget: 0 });
    const zero = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 999999,
      budget_cents: 0,
      now: FIXED_TS,
    });
    assert.equal(zero.breached, false);
    const negative = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: 999999,
      budget_cents: -1,
      now: FIXED_TS,
    });
    assert.equal(negative.breached, false);
  });

  it("rejects non-finite or negative spend silently (no breach)", () => {
    const task = makeTask();
    const nan = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: Number.NaN,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    assert.equal(nan.breached, false);
    const neg = onBudgetBreach(task, {
      task_id: "t1",
      spent_cents: -1,
      budget_cents: 1000,
      now: FIXED_TS,
    });
    assert.equal(neg.breached, false);
  });
});

// ---------- BUDGET_TOOL_DEFS shape ----------

describe("BUDGET_TOOL_DEFS", () => {
  it("exposes a single task_budget_report tool", () => {
    assert.equal(BUDGET_TOOL_DEFS.length, 1);
    assert.equal(BUDGET_TOOL_DEFS[0].name, "task_budget_report");
  });

  it("requires org_id, task_id, by, spent_cents, budget_cents", () => {
    const schema = BUDGET_TOOL_DEFS[0].inputSchema as Record<string, unknown>;
    assert.deepEqual(
      (schema.required as string[]).slice().sort(),
      ["budget_cents", "by", "org_id", "spent_cents", "task_id"],
    );
  });
});

// ---------- dispatchBudgetReport ----------

describe("dispatchBudgetReport", () => {
  it("POSTs to /api/orgs/:id/board/tasks/:tid/budget and returns escalated flag", async () => {
    let captured: any = null;
    const fetchStub = async (url: string, init: RequestInit) => {
      captured = { url: String(url), init };
      return {
        ok: true,
        status: 200,
        json: async () => ({ ok: true, escalated: true, ratio: 1.0 }),
      } as Response;
    };

    const result = await dispatchBudgetReport(
      {
        org_id: "o1",
        task_id: "t1",
        by: "agent-alice",
        spent_cents: 1000,
        budget_cents: 1000,
      },
      { fetch: fetchStub as typeof fetch, lensBase: "http://127.0.0.1:7880" },
    );
    assert.equal(result.tokens_used, 0);
    assert.ok("ok" in result && result.ok === true);
    assert.equal((result as any).escalated, true);
    assert.ok(captured);
    assert.ok(captured!.url.endsWith("/api/orgs/o1/board/tasks/t1/budget"));
    assert.equal(captured!.init.method, "POST");
  });

  it("returns invalid_argument on negative spend", async () => {
    const result = await dispatchBudgetReport({
      org_id: "o1",
      task_id: "t1",
      by: "x",
      spent_cents: -1,
      budget_cents: 1000,
    });
    assert.equal((result as any).error.code, "invalid_argument");
  });

  it("returns invalid_argument on non-finite budget", async () => {
    const result = await dispatchBudgetReport({
      org_id: "o1",
      task_id: "t1",
      by: "x",
      spent_cents: 1,
      budget_cents: Number.POSITIVE_INFINITY,
    });
    assert.equal((result as any).error.code, "invalid_argument");
  });

  it("surfaces upstream error envelope", async () => {
    const fetchStub = async () =>
      ({
        ok: false,
        status: 404,
        json: async () => ({ error: { code: "not_found", message: "task missing" } }),
      } as Response);
    const result = await dispatchBudgetReport(
      {
        org_id: "o1",
        task_id: "nope",
        by: "x",
        spent_cents: 1,
        budget_cents: 1,
      },
      { fetch: fetchStub as typeof fetch },
    );
    assert.equal((result as any).error.code, "not_found");
  });

  it("returns internal on network failure", async () => {
    const fetchStub = async () => {
      throw new Error("ECONNREFUSED");
    };
    const result = await dispatchBudgetReport(
      {
        org_id: "o1",
        task_id: "t1",
        by: "x",
        spent_cents: 1,
        budget_cents: 1,
      },
      { fetch: fetchStub as typeof fetch },
    );
    assert.equal((result as any).error.code, "internal");
  });
});

describe("dispatchBudget router", () => {
  it("returns unknown_tool for unrecognised names", async () => {
    const result = await dispatchBudget("not_a_tool", {});
    assert.equal((result as any).error.code, "unknown_tool");
  });
});
