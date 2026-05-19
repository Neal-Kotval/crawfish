import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createTask, updateTask } from "../src/tasks.js";
import { createCycle } from "../src/cycles.js";
import { parseQuery, searchTasks, rebuildIndex, incrementalUpdate } from "../src/search.js";
import { serializeFrontmatter } from "../src/frontmatter.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-search-"));
}

test("parseQuery: bare free text", () => {
  const p = parseQuery("hello world");
  assert.deepEqual(p.keyVals, {});
  assert.deepEqual(p.ops, []);
  assert.equal(p.freeText, "hello world");
});

test("parseQuery: key:value pairs + free text", () => {
  const p = parseQuery("assignee:engineer-1 label:bug cycle:current free text here");
  assert.equal(p.keyVals.assignee, "engineer-1");
  assert.equal(p.keyVals.label, "bug");
  assert.equal(p.keyVals.cycle, "current");
  assert.equal(p.freeText, "free text here");
});

test("parseQuery: priority>=high operator", () => {
  const p = parseQuery("priority>=high");
  assert.deepEqual(p.keyVals, {});
  assert.equal(p.ops.length, 1);
  assert.deepEqual(p.ops[0], { key: "priority", op: ">=", value: "high" });
});

test("parseQuery rejects comparator on non-orderable key", () => {
  assert.throws(() => parseQuery("assignee>=foo"), /invalid_operator/);
});

test("parseQuery: unknown key falls into freeText", () => {
  const p = parseQuery("randomkey:value other:thing");
  assert.equal(p.freeText.includes("randomkey:value"), true);
  assert.equal(p.freeText.includes("other:thing"), true);
});

test("searchTasks: structured filter by assignee + label", () => {
  const root = mkRoot();
  // Tasks need labels/priority/assignee — write via createTask + raw frontmatter for labels.
  const dir = join(root, ".crawfish", "tasks");
  mkdirSync(dir, { recursive: true });
  writeFileSync(
    join(dir, "t1.md"),
    serializeFrontmatter(
      { id: "t1", title: "Bug in login", status: "todo", labels: ["bug", "auth"], priority: "high", assignee: "engineer-1" },
      "# Bug in login\nDescription here.\n",
    ),
    "utf8",
  );
  writeFileSync(
    join(dir, "t2.md"),
    serializeFrontmatter(
      { id: "t2", title: "Feature work", status: "todo", labels: ["feature"], priority: "low", assignee: "engineer-2" },
      "# Feature\n",
    ),
    "utf8",
  );
  rebuildIndex(root);
  const r = searchTasks(root, "assignee:engineer-1 label:bug");
  assert.equal(r.results.length, 1);
  assert.equal(r.results[0].slug, "t1");
});

test("searchTasks: priority>=high keeps high & critical, drops low/med", () => {
  const root = mkRoot();
  const dir = join(root, ".crawfish", "tasks");
  mkdirSync(dir, { recursive: true });
  const mk = (slug: string, priority: string) =>
    writeFileSync(
      join(dir, `${slug}.md`),
      serializeFrontmatter({ id: slug, title: slug, status: "todo", priority }, "# x\n"),
      "utf8",
    );
  mk("low", "low");
  mk("med", "med");
  mk("high", "high");
  mk("crit", "critical");
  rebuildIndex(root);
  const r = searchTasks(root, "priority>=high");
  const slugs = r.results.map((t) => t.slug).sort();
  assert.deepEqual(slugs, ["crit", "high"]);
});

test("searchTasks: freeText FTS match on title/body", () => {
  const root = mkRoot();
  createTask(root, { slug: "alpha", title: "Refactor login flow", body: "# Refactor login\nReplace clerk SDK.\n" });
  createTask(root, { slug: "beta", title: "Update billing", body: "# Billing\nStripe integration.\n" });
  rebuildIndex(root);
  const r = searchTasks(root, "login");
  const slugs = r.results.map((t) => t.slug);
  assert.ok(slugs.includes("alpha"));
  assert.ok(!slugs.includes("beta"));
});

test("searchTasks: cycle:current resolves active cycle, warns when none", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1" });
  rebuildIndex(root);
  const r = searchTasks(root, "cycle:current");
  assert.equal(r.warnings.includes("cycle:current → no_active_cycle"), true);
});

test("searchTasks: cycle:current honors active cycle", () => {
  const root = mkRoot();
  const today = new Date().toISOString().slice(0, 10);
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  createCycle(root, { id: "cyc_A", name: "A", start: today, end: tomorrow, token_budget: 1000 });
  createTask(root, { slug: "in-cycle", title: "in", cycle: "cyc_A" });
  createTask(root, { slug: "out-cycle", title: "out" });
  rebuildIndex(root);
  const r = searchTasks(root, "cycle:current");
  const slugs = r.results.map((t) => t.slug);
  assert.ok(slugs.includes("in-cycle"));
  assert.ok(!slugs.includes("out-cycle"));
});

test("incrementalUpdate re-indexes a single task", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "old title", body: "# old\n" });
  rebuildIndex(root);
  updateTask(root, "t1", { title: "shiny new keyword zarquon" });
  incrementalUpdate(root, "t1");
  const r = searchTasks(root, "zarquon");
  assert.equal(r.results.length, 1);
  assert.equal(r.results[0].slug, "t1");
});

test("searchTasks limit caps at 50", () => {
  const root = mkRoot();
  for (let i = 0; i < 60; i++) {
    createTask(root, { slug: `task-${i}`, title: `task ${i}` });
  }
  rebuildIndex(root);
  const r = searchTasks(root, "");
  assert.ok(r.results.length <= 50);
});
