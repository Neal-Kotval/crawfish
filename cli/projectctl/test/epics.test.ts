import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createTask, updateTask } from "../src/tasks.js";
import { createEpic, listEpics, readEpic, updateEpic, computeEpicRollup } from "../src/epics.js";
import { readEvents } from "../src/project-board.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-epics-"));
}

test("createEpic writes .md and emits epic_created", () => {
  const root = mkRoot();
  const path = createEpic(root, { id: "epc_AUTH", title: "Auth refactor" });
  assert.ok(existsSync(path));
  const e = readEpic(root, "epc_AUTH");
  assert.equal(e?.title, "Auth refactor");
  assert.equal(e?.status, "open");
  assert.equal(e?.parent_cycle, null);
  const events = readEvents(root);
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "epic_created");
  assert.equal(events[0].epic_id, "epc_AUTH");
});

test("createEpic rejects invalid id", () => {
  const root = mkRoot();
  assert.throws(
    () => createEpic(root, { id: "not-an-epic", title: "x" }),
    /invalid_epic_id/,
  );
});

test("createEpic rejects duplicate id", () => {
  const root = mkRoot();
  createEpic(root, { id: "epc_A", title: "A" });
  assert.throws(
    () => createEpic(root, { id: "epc_A", title: "Different" }),
    /epic_already_exists/,
  );
});

test("createEpic with parent_cycle records the link", () => {
  const root = mkRoot();
  createEpic(root, { id: "epc_B", title: "B", parent_cycle: "cyc_01" });
  const e = readEpic(root, "epc_B");
  assert.equal(e?.parent_cycle, "cyc_01");
  const events = readEvents(root);
  assert.equal((events[0].payload as Record<string, unknown>).parent_cycle, "cyc_01");
});

test("listEpics sorts by id", () => {
  const root = mkRoot();
  createEpic(root, { id: "epc_Z", title: "Z" });
  createEpic(root, { id: "epc_A", title: "A" });
  const list = listEpics(root);
  assert.equal(list[0].id, "epc_A");
  assert.equal(list[1].id, "epc_Z");
});

test("updateEpic closes an epic and emits epic_closed", () => {
  const root = mkRoot();
  createEpic(root, { id: "epc_C", title: "C" });
  updateEpic(root, "epc_C", { status: "closed" });
  const e = readEpic(root, "epc_C");
  assert.equal(e?.status, "closed");
  const events = readEvents(root);
  const last2 = events.slice(-2).map((e) => e.type);
  assert.deepEqual(last2, ["epic_updated", "epic_closed"]);
});

test("updateEpic is idempotent — no events when nothing changes", () => {
  const root = mkRoot();
  createEpic(root, { id: "epc_D", title: "D" });
  updateEpic(root, "epc_D", { title: "D" });
  const events = readEvents(root);
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "epic_created");
});

test("updateEpic parent_cycle: null unsets the parent", () => {
  const root = mkRoot();
  createEpic(root, { id: "epc_E", title: "E", parent_cycle: "cyc_X" });
  updateEpic(root, "epc_E", { parent_cycle: null });
  const e = readEpic(root, "epc_E");
  assert.equal(e?.parent_cycle, null);
});

test("computeEpicRollup aggregates tasks pointing at this epic", () => {
  const root = mkRoot();
  createEpic(root, { id: "epc_F", title: "F" });
  createTask(root, { slug: "t1", title: "T1", estimate: 1000, epic: "epc_F", status: "doing" });
  createTask(root, { slug: "t2", title: "T2", estimate: 500, epic: "epc_F", status: "done" });
  createTask(root, { slug: "t3", title: "T3", estimate: 9999, epic: "epc_OTHER" });
  createTask(root, { slug: "t4", title: "T4", estimate: 200, epic: "epc_F", status: "blocked" });
  const r = computeEpicRollup(root, "epc_F");
  assert.equal(r?.task_count, 3);
  assert.equal(r?.estimate_used, 1700);
  assert.equal(r?.by_status.doing, 1);
  assert.equal(r?.by_status.done, 1);
  assert.equal(r?.by_status.blocked, 1);
  assert.equal(r?.by_status.todo, 0);
});

test("updateTask assigning epic is visible in rollup", () => {
  const root = mkRoot();
  createEpic(root, { id: "epc_G", title: "G" });
  createTask(root, { slug: "t1", title: "T1", estimate: 750 });
  let r = computeEpicRollup(root, "epc_G");
  assert.equal(r?.task_count, 0);
  updateTask(root, "t1", { epic: "epc_G" });
  r = computeEpicRollup(root, "epc_G");
  assert.equal(r?.task_count, 1);
  assert.equal(r?.estimate_used, 750);
});

test("computeEpicRollup returns null for unknown epic", () => {
  const root = mkRoot();
  assert.equal(computeEpicRollup(root, "epc_GHOST"), null);
});
