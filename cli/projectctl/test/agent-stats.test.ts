import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { appendEvent } from "../src/project-board.js";
import { serializeFrontmatter } from "../src/frontmatter.js";
import { getAgentStats, getAllAgentStats, listKnownAgents } from "../src/agent-stats.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-agent-stats-"));
}

function writeTaskFile(
  root: string,
  slug: string,
  fm: Record<string, unknown>,
): void {
  const dir = join(root, ".crawfish", "tasks");
  mkdirSync(dir, { recursive: true });
  // serializer types are narrow; cast via unknown.
  const raw = serializeFrontmatter(fm as never, `# ${slug}\n`);
  writeFileSync(join(dir, `${slug}.md`), raw, "utf8");
}

function emit(
  root: string,
  type: string,
  taskId: string,
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

test("getAgentStats returns empty when no events", () => {
  const root = mkRoot();
  const s = getAgentStats(root, "alice");
  assert.deepEqual(s.byLabel, {});
});

test("getAgentStats attributes done tasks to last assignee with labels", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", labels: ["frontend"], estimate: 1000 });
  writeTaskFile(root, "t2", { id: "t2", title: "T2", labels: ["frontend"], estimate: 2000 });
  emit(root, "task_assigned", "t1", { from: null, to: "alice", by: "router" }, 1);
  emit(root, "task_status_changed", "t1", { from: "doing", to: "done" }, 1);
  emit(root, "task_assigned", "t2", { from: null, to: "alice", by: "router" }, 2);
  emit(root, "task_status_changed", "t2", { from: "doing", to: "done" }, 2);

  const s = getAgentStats(root, "alice");
  assert.equal(s.byLabel.frontend?.n, 2);
  assert.equal(s.byLabel.frontend?.success_rate, 1.0);
  assert.equal(s.byLabel.frontend?.avg_tokens_per_task, 1500);
});

test("getAgentStats ignores events outside the 30-day window", () => {
  const root = mkRoot();
  writeTaskFile(root, "old", { id: "old", title: "Old", labels: ["frontend"], estimate: 500 });
  emit(root, "task_assigned", "old", { to: "alice" }, 60);
  emit(root, "task_status_changed", "old", { to: "done" }, 60);
  const s = getAgentStats(root, "alice");
  assert.equal(s.byLabel.frontend, undefined);
});

test("getAgentStats omits labels with n=0 (other agents' work)", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", labels: ["backend"], estimate: 1000 });
  emit(root, "task_assigned", "t1", { to: "bob" }, 1);
  emit(root, "task_status_changed", "t1", { to: "done" }, 1);
  const s = getAgentStats(root, "alice");
  assert.deepEqual(s.byLabel, {});
});

test("reassignment: final assignee at done-time wins attribution", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", labels: ["frontend"], estimate: 800 });
  emit(root, "task_assigned", "t1", { to: "alice" }, 3);
  emit(root, "task_assigned", "t1", { to: "bob" }, 2);
  emit(root, "task_status_changed", "t1", { to: "done" }, 1);
  const a = getAgentStats(root, "alice");
  const b = getAgentStats(root, "bob");
  assert.equal(a.byLabel.frontend, undefined);
  assert.equal(b.byLabel.frontend?.n, 1);
});

test("multi-label task counts in every label bucket", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", labels: ["frontend", "ui"], estimate: 1200 });
  emit(root, "task_assigned", "t1", { to: "alice" }, 1);
  emit(root, "task_status_changed", "t1", { to: "done" }, 1);
  const s = getAgentStats(root, "alice");
  assert.equal(s.byLabel.frontend?.n, 1);
  assert.equal(s.byLabel.ui?.n, 1);
});

test("getAllAgentStats batches all agents in one pass", () => {
  const root = mkRoot();
  writeTaskFile(root, "t1", { id: "t1", title: "T1", labels: ["frontend"], estimate: 1000 });
  writeTaskFile(root, "t2", { id: "t2", title: "T2", labels: ["frontend"], estimate: 2000 });
  emit(root, "task_assigned", "t1", { to: "alice" }, 1);
  emit(root, "task_status_changed", "t1", { to: "done" }, 1);
  emit(root, "task_assigned", "t2", { to: "bob" }, 1);
  emit(root, "task_status_changed", "t2", { to: "done" }, 1);
  const all = getAllAgentStats(root);
  assert.equal(all.get("alice")?.byLabel.frontend?.n, 1);
  assert.equal(all.get("bob")?.byLabel.frontend?.n, 1);
});

test("listKnownAgents returns sorted unique assignees", () => {
  const root = mkRoot();
  emit(root, "task_assigned", "t1", { to: "charlie" }, 1);
  emit(root, "task_assigned", "t2", { to: "alice" }, 1);
  emit(root, "task_assigned", "t3", { to: "alice" }, 1);
  emit(root, "task_assigned", "t4", { to: "bob" }, 1);
  assert.deepEqual(listKnownAgents(root), ["alice", "bob", "charlie"]);
});
