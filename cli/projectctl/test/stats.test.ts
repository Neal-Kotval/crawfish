import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { appendEvent } from "../src/project-board.js";
import { serializeFrontmatter } from "../src/frontmatter.js";
import { getStats } from "../src/stats.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-stats-"));
}

function writeTaskFile(
  root: string,
  slug: string,
  fm: Record<string, unknown>,
): void {
  const dir = join(root, ".crawfish", "tasks");
  mkdirSync(dir, { recursive: true });
  const raw = serializeFrontmatter(fm as never, `# ${slug}\n`);
  writeFileSync(join(dir, `${slug}.md`), raw, "utf8");
}

function emit(
  root: string,
  type: string,
  taskId: string | undefined,
  payload: Record<string, unknown>,
  daysAgo = 0,
): void {
  const ts = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000).toISOString();
  appendEvent(root, {
    ts,
    actor: "test",
    type: type as never,
    task_id: taskId,
    payload,
  });
}

test("getStats(dev) returns zeros on empty repo", () => {
  const root = mkRoot();
  const s = getStats(root, "dev");
  assert.deepEqual(s.tokens_by_agent, {});
  assert.deepEqual(s.tokens_by_tool, {});
  assert.equal(s.success_rate, 0);
});

test("getStats(product) returns zeros on empty repo", () => {
  const root = mkRoot();
  const s = getStats(root, "product");
  assert.equal(s.completion_rate, 0);
  assert.equal(s.escalation_rate, 0);
  assert.deepEqual(s.tasks_by_status, { todo: 0, doing: 0, done: 0, blocked: 0 });
});

test("dev.tokens_by_agent sums task estimate per current in-window assignee", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", estimate: 1000 });
  writeTaskFile(root, "t2", { id: "t2", title: "T2", estimate: 2000 });
  writeTaskFile(root, "t3", { id: "t3", title: "T3", estimate: 500 });
  emit(root, "task_assigned", "t1", { to: "alice" }, 1);
  emit(root, "task_assigned", "t2", { to: "alice" }, 1);
  emit(root, "task_assigned", "t3", { to: "bob" }, 1);
  const s = getStats(root, "dev");
  assert.equal(s.tokens_by_agent.alice, 3000);
  assert.equal(s.tokens_by_agent.bob, 500);
});

test("dev.tokens_by_agent ignores assignments outside the 30-day window", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", estimate: 1000 });
  emit(root, "task_assigned", "t1", { to: "alice" }, 60);
  const s = getStats(root, "dev");
  assert.deepEqual(s.tokens_by_agent, {});
});

test("dev.tokens_by_agent uses final in-window assignee", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", estimate: 1000 });
  emit(root, "task_assigned", "t1", { to: "alice" }, 3);
  emit(root, "task_assigned", "t1", { to: "bob" }, 1);
  const s = getStats(root, "dev");
  assert.equal(s.tokens_by_agent.alice, undefined);
  assert.equal(s.tokens_by_agent.bob, 1000);
});

test("dev.tokens_by_tool aggregates events that carry a tool field", () => {
  const root = mkRoot();
  emit(root, "task_updated", "t1", { tool: "grep", tokens: 100 }, 1);
  emit(root, "task_updated", "t1", { tool: "grep", tokens: 250 }, 2);
  emit(root, "task_updated", "t1", { tool: "read", tokens: 800 }, 1);
  const s = getStats(root, "dev");
  assert.equal(s.tokens_by_tool.grep, 350);
  assert.equal(s.tokens_by_tool.read, 800);
});

test("dev.tokens_by_tool is empty when no events carry tool data", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", estimate: 1000 });
  emit(root, "task_assigned", "t1", { to: "alice" }, 1);
  emit(root, "task_status_changed", "t1", { to: "done" }, 1);
  const s = getStats(root, "dev");
  assert.deepEqual(s.tokens_by_tool, {});
});

test("dev.success_rate = done / (done + escalated) inside the window", () => {
  const root = mkRoot();
  emit(root, "task_status_changed", "t1", { to: "done" }, 1);
  emit(root, "task_status_changed", "t2", { to: "done" }, 1);
  emit(root, "task_status_changed", "t3", { to: "done" }, 1);
  emit(root, "task_status_changed", "t4", { to: "escalated" }, 1);
  const s = getStats(root, "dev");
  assert.equal(s.success_rate, 0.75);
});

test("dev.success_rate ignores status transitions outside the window", () => {
  const root = mkRoot();
  emit(root, "task_status_changed", "t1", { to: "done" }, 60);
  emit(root, "task_status_changed", "t2", { to: "escalated" }, 60);
  const s = getStats(root, "dev");
  assert.equal(s.success_rate, 0);
});

test("product.completion_rate = closed / opened (window)", () => {
  const root = mkRoot();
  emit(root, "task_created", "t1", { title: "T1" }, 5);
  emit(root, "task_created", "t2", { title: "T2" }, 5);
  emit(root, "task_created", "t3", { title: "T3" }, 5);
  emit(root, "task_created", "t4", { title: "T4" }, 5);
  emit(root, "task_status_changed", "t1", { to: "done" }, 1);
  emit(root, "task_status_changed", "t2", { to: "escalated" }, 1);
  const s = getStats(root, "product");
  assert.equal(s.completion_rate, 0.5);
});

test("product.escalation_rate counts unique tasks that hit escalated", () => {
  const root = mkRoot();
  emit(root, "task_created", "t1", { title: "T1" }, 5);
  emit(root, "task_created", "t2", { title: "T2" }, 5);
  emit(root, "task_status_changed", "t1", { to: "escalated" }, 2);
  emit(root, "task_status_changed", "t1", { to: "escalated" }, 1); // duplicate same task
  const s = getStats(root, "product");
  assert.equal(s.escalation_rate, 0.5);
});

test("product rates are 0 (not NaN) when no tasks opened in window", () => {
  const root = mkRoot();
  emit(root, "task_status_changed", "t1", { to: "done" }, 1);
  const s = getStats(root, "product");
  assert.equal(s.completion_rate, 0);
  assert.equal(s.escalation_rate, 0);
});

test("product.tasks_by_status snapshots current task tree", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", status: "todo" });
  writeTaskFile(root, "t2", { id: "t2", title: "T2", status: "doing" });
  writeTaskFile(root, "t3", { id: "t3", title: "T3", status: "done" });
  writeTaskFile(root, "t4", { id: "t4", title: "T4", status: "done" });
  writeTaskFile(root, "t5", { id: "t5", title: "T5", status: "blocked" });
  const s = getStats(root, "product");
  assert.deepEqual(s.tasks_by_status, { todo: 1, doing: 1, done: 2, blocked: 1 });
});

test("getStats accepts injectable clock via opts.now", () => {
  const root = mkRoot();
  emit(root, "task_status_changed", "t1", { to: "done" }, 10);
  // Fast-forward 40 days into the future; the event is now > 30 days old.
  const future = Date.now() + 40 * 24 * 60 * 60 * 1000;
  const s = getStats(root, "dev", { now: future });
  assert.equal(s.success_rate, 0);
});
