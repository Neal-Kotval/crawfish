import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { appendEvent, readEvents } from "../src/project-board.js";
import { serializeFrontmatter, parseFrontmatter } from "../src/frontmatter.js";
import { pickAssignee, runRouterPass, type RoutableTask } from "../src/router.js";
import type { AgentStats } from "../src/agent-stats.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-router-"));
}

function writeTaskFile(root: string, slug: string, fm: Record<string, unknown>): void {
  const dir = join(root, ".crawfish", "tasks");
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${slug}.md`), serializeFrontmatter(fm as never, `# ${slug}\n`), "utf8");
}

function emit(root: string, type: string, taskId: string, payload: Record<string, unknown>, daysAgo = 0): void {
  const ts = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000).toISOString();
  appendEvent(root, { ts, actor: "test", type: type as never, task_id: taskId, payload });
}

const task = (id: string, labels: string[]): RoutableTask => ({ id, labels, status: "todo", assignee: null });

test("pickAssignee returns null when task has no labels", () => {
  const result = pickAssignee(task("t1", []), new Map(), ["alice"]);
  assert.equal(result, null);
});

test("pickAssignee filters out agents below 0.7 success_rate", () => {
  const stats = new Map<string, AgentStats>([
    ["alice", { byLabel: { frontend: { success_rate: 0.5, avg_tokens_per_task: 100, n: 10 } } }],
    ["bob", { byLabel: { frontend: { success_rate: 0.7, avg_tokens_per_task: 100, n: 10 } } }],
  ]);
  // 0.7 is NOT > 0.7 — strict inequality per contract.
  const result = pickAssignee(task("t1", ["frontend"]), stats, ["alice", "bob"]);
  assert.equal(result, null);
});

test("pickAssignee picks lowest avg_tokens among qualified", () => {
  const stats = new Map<string, AgentStats>([
    ["alice", { byLabel: { frontend: { success_rate: 0.9, avg_tokens_per_task: 200, n: 5 } } }],
    ["bob", { byLabel: { frontend: { success_rate: 0.8, avg_tokens_per_task: 100, n: 5 } } }],
  ]);
  assert.equal(pickAssignee(task("t1", ["frontend"]), stats, ["alice", "bob"]), "bob");
});

test("pickAssignee tie-breaks by least load then by sorted id", () => {
  const stats = new Map<string, AgentStats>([
    ["alice", { byLabel: { frontend: { success_rate: 0.9, avg_tokens_per_task: 100, n: 5 } } }],
    ["bob", { byLabel: { frontend: { success_rate: 0.9, avg_tokens_per_task: 100, n: 5 } } }],
    ["zach", { byLabel: { frontend: { success_rate: 0.9, avg_tokens_per_task: 100, n: 5 } } }],
  ]);
  // Equal avg + bob has higher load → alice wins (least load + alphabetical).
  const load = new Map([["alice", 0], ["bob", 3], ["zach", 0]]);
  assert.equal(
    pickAssignee(task("t1", ["frontend"]), stats, ["alice", "bob", "zach"], { load }),
    "alice",
  );
});

test("pickAssignee returns null when no candidate has stats for the label", () => {
  const stats = new Map<string, AgentStats>([
    ["alice", { byLabel: { backend: { success_rate: 1.0, avg_tokens_per_task: 50, n: 5 } } }],
  ]);
  assert.equal(pickAssignee(task("t1", ["frontend"]), stats, ["alice"]), null);
});

test("pickAssignee uses primary (first) label only", () => {
  const stats = new Map<string, AgentStats>([
    ["alice", { byLabel: { frontend: { success_rate: 0.9, avg_tokens_per_task: 100, n: 5 } } }],
  ]);
  // First label is 'ui' (unknown to alice) → null even though 'frontend' is second.
  assert.equal(pickAssignee({ id: "t1", labels: ["ui", "frontend"], status: "todo" }, stats, ["alice"]), null);
});

test("runRouterPass writes assignee and emits task_assigned with by:router", () => {
  const root = mkRoot();
  // Seed historical stats: alice + frontend, n=3, success=1.0.
  for (let i = 0; i < 3; i++) {
    const slug = `done-${i}`;
    writeTaskFile(root, slug, { id: slug, title: slug, status: "done", labels: ["frontend"], estimate: 1000, assignee: "alice" });
    emit(root, "task_assigned", slug, { to: "alice" }, 5);
    emit(root, "task_status_changed", slug, { to: "done" }, 4);
  }
  writeTaskFile(root, "new", { id: "new", title: "new", status: "todo", labels: ["frontend"], estimate: 800 });

  const result = runRouterPass(root);
  assert.equal(result.scanned, 1);
  assert.equal(result.assigned, 1);
  assert.equal(result.skipped.length, 0);

  const taskFile = readFileSync(join(root, ".crawfish", "tasks", "new.md"), "utf8");
  const { fm } = parseFrontmatter(taskFile);
  assert.equal(fm.assignee, "alice");

  const evs = readEvents(root);
  const assigned = evs.filter((e) => e.type === "task_assigned" && e.task_id === "new");
  assert.equal(assigned.length, 1);
  assert.equal((assigned[0].payload as Record<string, unknown>).by, "router");
  assert.equal((assigned[0].payload as Record<string, unknown>).to, "alice");
});

test("runRouterPass skips tasks with no labels", () => {
  const root = mkRoot();
  writeTaskFile(root, "nolab", { id: "nolab", title: "x", status: "todo", estimate: 100 });
  const result = runRouterPass(root);
  assert.equal(result.scanned, 1);
  assert.equal(result.assigned, 0);
  assert.deepEqual(result.skipped, [{ taskId: "nolab", reason: "no_label" }]);
});

test("runRouterPass skips when no agent qualifies", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", status: "todo", labels: ["frontend"], estimate: 800 });
  const result = runRouterPass(root, { agents: ["alice"] });
  assert.equal(result.assigned, 0);
  assert.deepEqual(result.skipped, [{ taskId: "t1", reason: "no_qualified_candidate" }]);
});

test("runRouterPass skips already-assigned tasks", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", status: "todo", labels: ["frontend"], estimate: 800, assignee: "bob" });
  const result = runRouterPass(root);
  assert.equal(result.assigned, 0);
  assert.deepEqual(result.skipped, [{ taskId: "t1", reason: "already_assigned" }]);
});

test("runRouterPass ignores done/doing tasks (only todo/triage are routable)", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", status: "doing", labels: ["frontend"], estimate: 800 });
  writeTaskFile(root, "t2", { id: "t2", title: "T2", status: "done", labels: ["frontend"], estimate: 800 });
  const result = runRouterPass(root);
  assert.equal(result.scanned, 0);
});

test("runRouterPass dryRun does not mutate", () => {
  const root = mkRoot();
  for (let i = 0; i < 3; i++) {
    const slug = `done-${i}`;
    writeTaskFile(root, slug, { id: slug, title: slug, status: "done", labels: ["frontend"], estimate: 1000, assignee: "alice" });
    emit(root, "task_assigned", slug, { to: "alice" }, 5);
    emit(root, "task_status_changed", slug, { to: "done" }, 4);
  }
  writeTaskFile(root, "new", { id: "new", title: "new", status: "todo", labels: ["frontend"], estimate: 800 });
  const before = readFileSync(join(root, ".crawfish", "tasks", "new.md"), "utf8");
  const result = runRouterPass(root, { dryRun: true });
  assert.equal(result.assigned, 1);
  const after = readFileSync(join(root, ".crawfish", "tasks", "new.md"), "utf8");
  assert.equal(before, after);
});
