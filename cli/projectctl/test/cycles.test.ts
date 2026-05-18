import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createTask, updateTask } from "../src/tasks.js";
import { createCycle, listCycles, readCycle, computeRollup } from "../src/cycles.js";
import { readEvents } from "../src/project-board.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-cycles-"));
}

test("createCycle writes JSON and emits cycle_created", () => {
  const root = mkRoot();
  const c = createCycle(root, {
    id: "cyc_01H1",
    name: "May Sprint",
    start: "2026-05-18",
    end: "2026-05-25",
    token_budget: 50000,
  });
  assert.equal(c.status, "open");
  assert.ok(existsSync(join(root, ".crawfish", "cycles", "cyc_01H1.json")));
  const events = readEvents(root);
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "cycle_created");
  assert.equal(events[0].cycle_id, "cyc_01H1");
});

test("createCycle rejects invalid id", () => {
  const root = mkRoot();
  assert.throws(
    () => createCycle(root, {
      id: "not-a-cycle",
      name: "X",
      start: "2026-05-18",
      end: "2026-05-25",
      token_budget: 1000,
    }),
    /invalid_cycle_id/,
  );
});

test("listCycles returns cycles sorted by start", () => {
  const root = mkRoot();
  createCycle(root, { id: "cyc_B", name: "B", start: "2026-06-01", end: "2026-06-07", token_budget: 1000 });
  createCycle(root, { id: "cyc_A", name: "A", start: "2026-05-01", end: "2026-05-07", token_budget: 1000 });
  const list = listCycles(root);
  assert.equal(list.length, 2);
  assert.equal(list[0].id, "cyc_A");
  assert.equal(list[1].id, "cyc_B");
});

test("computeRollup sums task estimates for cycle assignment", () => {
  const root = mkRoot();
  createCycle(root, { id: "cyc_X", name: "X", start: "2026-05-18", end: "2026-05-25", token_budget: 10000 });
  createTask(root, { slug: "t1", title: "T1", estimate: 3000, cycle: "cyc_X", status: "todo" });
  createTask(root, { slug: "t2", title: "T2", estimate: 4000, cycle: "cyc_X", status: "doing" });
  createTask(root, { slug: "t3", title: "T3", estimate: 9999, cycle: "cyc_OTHER" }); // not in cyc_X
  createTask(root, { slug: "t4", title: "T4", estimate: 2000, cycle: "cyc_X", status: "done" });

  const r = computeRollup(root, "cyc_X");
  assert.ok(r);
  assert.equal(r!.task_count, 3);
  assert.equal(r!.estimate_used, 9000);
  assert.equal(r!.estimate_remaining, 1000);
  assert.equal(r!.pct_used, 90);
  assert.equal(r!.overspent, false);
  assert.equal(r!.by_status.todo, 1);
  assert.equal(r!.by_status.doing, 1);
  assert.equal(r!.by_status.done, 1);
});

test("computeRollup flags overspent when estimates exceed budget", () => {
  const root = mkRoot();
  createCycle(root, { id: "cyc_T", name: "Tight", start: "2026-05-18", end: "2026-05-25", token_budget: 1000 });
  createTask(root, { slug: "big", title: "Big", estimate: 5000, cycle: "cyc_T" });
  const r = computeRollup(root, "cyc_T");
  assert.equal(r!.overspent, true);
  assert.equal(r!.estimate_remaining, -4000);
});

test("computeRollup returns null for unknown cycle", () => {
  const root = mkRoot();
  assert.equal(computeRollup(root, "cyc_GHOST"), null);
});

test("assigning a task to a cycle via updateTask is visible in rollup", () => {
  const root = mkRoot();
  createCycle(root, { id: "cyc_M", name: "M", start: "2026-05-18", end: "2026-05-25", token_budget: 10000 });
  createTask(root, { slug: "t1", title: "T1", estimate: 1500 });
  let r = computeRollup(root, "cyc_M");
  assert.equal(r!.task_count, 0);
  updateTask(root, "t1", { cycle: "cyc_M" });
  r = computeRollup(root, "cyc_M");
  assert.equal(r!.task_count, 1);
  assert.equal(r!.estimate_used, 1500);
});

test("readCycle parses round-tripped JSON cleanly", () => {
  const root = mkRoot();
  createCycle(root, { id: "cyc_R", name: "Read", start: "2026-05-18", end: "2026-05-25", token_budget: 1234 });
  const raw = readFileSync(join(root, ".crawfish", "cycles", "cyc_R.json"), "utf8");
  assert.ok(raw.includes("\"id\": \"cyc_R\""));
  const c = readCycle(root, "cyc_R");
  assert.equal(c?.token_budget, 1234);
});
