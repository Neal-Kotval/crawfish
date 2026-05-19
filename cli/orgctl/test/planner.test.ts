import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  PLANNER_TOOL_DEFS,
  dispatchPlanner,
  decomposeEpic,
} from "../src/planner.js";

describe("PLANNER_TOOL_DEFS", () => {
  it("exposes planner_decompose", () => {
    assert.equal(PLANNER_TOOL_DEFS.length, 1);
    assert.equal(PLANNER_TOOL_DEFS[0].name, "planner_decompose");
  });

  it("description is substantial", () => {
    assert.ok((PLANNER_TOOL_DEFS[0].description?.length ?? 0) > 80);
  });

  it("requires epic", () => {
    const schema = PLANNER_TOOL_DEFS[0].inputSchema as Record<string, unknown>;
    assert.deepEqual(schema.required, ["epic"]);
  });
});

describe("decomposeEpic — Add prefix", () => {
  it("produces a 4-subtask DAG for 'Add X'", () => {
    const p = decomposeEpic({ id: "e1", title: "Add dark mode" });
    assert.equal(p.subtasks.length, 4);
    assert.equal(p.subtasks[0].title, "Design dark mode");
    assert.equal(p.subtasks[1].title, "Implement dark mode");
    assert.deepEqual(p.subtasks[1].depends_on, ["s1"]);
    assert.equal(p.subtasks[2].title, "Test dark mode");
    assert.deepEqual(p.subtasks[2].depends_on, ["s2"]);
    assert.equal(p.subtasks[3].title, "Document dark mode");
    assert.deepEqual(p.subtasks[3].depends_on, ["s2"]);
  });

  it("ids are s1..s4 and stable", () => {
    const p = decomposeEpic({ id: "e1", title: "Add CSV export" });
    assert.deepEqual(
      p.subtasks.map((s) => s.id),
      ["s1", "s2", "s3", "s4"],
    );
  });

  it("matches case-insensitively", () => {
    const p = decomposeEpic({ id: "e1", title: "ADD foo" });
    assert.equal(p.subtasks.length, 4);
  });
});

describe("decomposeEpic — Refactor prefix", () => {
  it("produces a 3-subtask DAG for 'Refactor X'", () => {
    const p = decomposeEpic({ id: "e1", title: "Refactor billing module" });
    assert.equal(p.subtasks.length, 3);
    assert.equal(p.subtasks[0].title, "Identify call sites of billing module");
    assert.equal(p.subtasks[1].title, "Refactor billing module");
    assert.deepEqual(p.subtasks[1].depends_on, ["s1"]);
    assert.equal(p.subtasks[2].title, "Update tests for billing module");
    assert.deepEqual(p.subtasks[2].depends_on, ["s2"]);
  });
});

describe("decomposeEpic — fallback", () => {
  it("produces a generic 3-subtask DAG otherwise", () => {
    const p = decomposeEpic({ id: "e1", title: "Investigate flaky CI" });
    assert.equal(p.subtasks.length, 3);
    assert.deepEqual(
      p.subtasks.map((s) => s.id),
      ["s1", "s2", "s3"],
    );
    assert.deepEqual(p.subtasks[2].depends_on, ["s2"]);
  });

  it("rationale is present on every branch", () => {
    for (const title of ["Add x", "Refactor y", "Generic thing"]) {
      const p = decomposeEpic({ id: "e1", title });
      assert.ok(typeof p.rationale === "string" && p.rationale.length > 0);
    }
  });

  it("depends_on only references earlier ids", () => {
    for (const title of ["Add x", "Refactor y", "Generic thing"]) {
      const p = decomposeEpic({ id: "e1", title });
      const seen = new Set<string>();
      for (const s of p.subtasks) {
        for (const dep of s.depends_on ?? []) {
          assert.ok(seen.has(dep), `subtask ${s.id} depends_on ${dep} which is not earlier`);
        }
        seen.add(s.id);
      }
    }
  });
});

describe("dispatchPlanner", () => {
  it("returns ok envelope on valid epic", async () => {
    const res = await dispatchPlanner("planner_decompose", {
      epic: { id: "e1", title: "Add foo" },
    });
    assert.ok("ok" in res && res.ok);
    if ("ok" in res) {
      assert.equal(res.result.subtasks.length, 4);
    }
  });

  it("rejects missing epic", async () => {
    const res = await dispatchPlanner("planner_decompose", {});
    assert.ok("error" in res);
    if ("error" in res) assert.equal(res.error.code, "invalid_argument");
  });

  it("rejects missing epic.id", async () => {
    const res = await dispatchPlanner("planner_decompose", { epic: { title: "x" } });
    assert.ok("error" in res);
  });

  it("rejects missing epic.title", async () => {
    const res = await dispatchPlanner("planner_decompose", { epic: { id: "e1" } });
    assert.ok("error" in res);
  });

  it("returns unknown_tool for other names", async () => {
    const res = await dispatchPlanner("nope", { epic: { id: "e1", title: "x" } });
    assert.ok("error" in res);
    if ("error" in res) assert.equal(res.error.code, "unknown_tool");
  });
});
