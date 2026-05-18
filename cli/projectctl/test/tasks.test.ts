import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import {
  createTask,
  updateTask,
  renameTask,
  deleteTask,
  readTask,
} from "../src/tasks.js";
import { readEvents } from "../src/project-board.js";
import { parseFrontmatter, serializeFrontmatter } from "../src/frontmatter.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-tasks-"));
}

test("createTask writes .md file and appends task_created event", () => {
  const root = mkRoot();
  const path = createTask(root, {
    slug: "implement-cycle-schema",
    title: "Implement cycle schema",
    status: "todo",
    estimate: 5000,
    phase: "now",
  });
  assert.ok(existsSync(path));
  const raw = readFileSync(path, "utf8");
  const { fm } = parseFrontmatter(raw);
  assert.equal(fm.id, "implement-cycle-schema");
  assert.equal(fm.title, "Implement cycle schema");
  assert.equal(fm.status, "todo");
  assert.equal(fm.estimate, 5000);

  const events = readEvents(root);
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "task_created");
  assert.equal(events[0].task_id, "implement-cycle-schema");
});

test("createTask rejects invalid slugs", () => {
  const root = mkRoot();
  assert.throws(
    () => createTask(root, { slug: "Bad Slug!", title: "x" }),
    /invalid_task_slug/,
  );
});

test("createTask rejects duplicate slugs", () => {
  const root = mkRoot();
  createTask(root, { slug: "a", title: "A" });
  assert.throws(
    () => createTask(root, { slug: "a", title: "Different" }),
    /task_already_exists/,
  );
});

test("updateTask emits task_status_changed and updates frontmatter", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", status: "todo" });
  updateTask(root, "t1", { status: "doing" });
  const t = readTask(root, "t1");
  assert.equal(t?.frontmatter.status, "doing");
  const events = readEvents(root);
  assert.equal(events.length, 3); // created, updated, status_changed
  assert.deepEqual(
    events.map((e) => e.type),
    ["task_created", "task_updated", "task_status_changed"],
  );
});

test("updateTask is idempotent — no events when nothing changes", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", status: "doing" });
  updateTask(root, "t1", { status: "doing" });
  const events = readEvents(root);
  assert.equal(events.length, 1);
  assert.equal(events[0].type, "task_created");
});

test("updateTask assigns/reassigns cycle and emits cycle events", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1" });
  updateTask(root, "t1", { cycle: "cyc_A" });
  let events = readEvents(root);
  assert.deepEqual(
    events.map((e) => e.type),
    ["task_created", "task_updated", "task_added_to_cycle"],
  );

  updateTask(root, "t1", { cycle: "cyc_B" });
  events = readEvents(root);
  const last4 = events.slice(-3).map((e) => e.type);
  assert.deepEqual(last4, [
    "task_updated",
    "task_removed_from_cycle",
    "task_added_to_cycle",
  ]);
});

test("updateTask cycle: null unassigns", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", cycle: "cyc_A" });
  updateTask(root, "t1", { cycle: null });
  const t = readTask(root, "t1");
  assert.equal(t?.frontmatter.cycle, undefined);
  const events = readEvents(root);
  const lastTypes = events.slice(-2).map((e) => e.type);
  assert.deepEqual(lastTypes, ["task_updated", "task_removed_from_cycle"]);
});

test("renameTask updates id frontmatter and emits task_renamed", () => {
  const root = mkRoot();
  createTask(root, { slug: "old", title: "Old" });
  renameTask(root, "old", "new-slug");
  assert.equal(readTask(root, "old"), null);
  const t = readTask(root, "new-slug");
  assert.equal(t?.frontmatter.id, "new-slug");
  const events = readEvents(root);
  assert.equal(events[events.length - 1].type, "task_renamed");
});

test("deleteTask removes file and emits task_deleted", () => {
  const root = mkRoot();
  createTask(root, { slug: "doomed", title: "Bye" });
  deleteTask(root, "doomed");
  assert.equal(readTask(root, "doomed"), null);
  const events = readEvents(root);
  assert.equal(events[events.length - 1].type, "task_deleted");
});

test("frontmatter round-trips arrays and numbers", () => {
  const fm = {
    id: "t1",
    title: "T1",
    estimate: 1500,
    "depends-on": ["a", "b"],
  };
  const raw = serializeFrontmatter(fm, "# body\n");
  const { fm: parsed, body } = parseFrontmatter(raw);
  assert.equal(parsed.id, "t1");
  assert.equal(parsed.estimate, 1500);
  assert.deepEqual(parsed["depends-on"], ["a", "b"]);
  assert.equal(body.trim(), "# body");
});

test("CRAWFISH_ACTOR env var is honored when set", () => {
  const root = mkRoot();
  process.env.CRAWFISH_ACTOR = "alice";
  try {
    createTask(root, { slug: "t1", title: "T1" });
    const events = readEvents(root);
    assert.equal(events[0].actor, "alice");
  } finally {
    delete process.env.CRAWFISH_ACTOR;
  }
});

test("per-call actor override does not leak", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", actor: "alice" });
  createTask(root, { slug: "t2", title: "T2" });
  const events = readEvents(root);
  assert.equal(events[0].actor, "alice");
  assert.equal(events[1].actor, "local");
});
