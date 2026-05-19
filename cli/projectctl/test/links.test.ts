import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createTask, readTask, readTaskLinks } from "../src/tasks.js";
import { addLink, removeLink, reciprocalKind, validateLinkInput } from "../src/links.js";
import { readEvents } from "../src/project-board.js";
import { parseFrontmatter, serializeFrontmatter, type TaskLink } from "../src/frontmatter.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-links-"));
}

test("reciprocalKind: blocks ↔ depends_on, reflexive for duplicates/relates_to, null for subtask_of", () => {
  assert.equal(reciprocalKind("blocks"), "depends_on");
  assert.equal(reciprocalKind("depends_on"), "blocks");
  assert.equal(reciprocalKind("duplicates"), "duplicates");
  assert.equal(reciprocalKind("relates_to"), "relates_to");
  assert.equal(reciprocalKind("subtask_of"), null);
});

test("validateLinkInput rejects self-link, invalid kind, missing target", () => {
  assert.throws(() => validateLinkInput("a", { kind: "blocks", target_task_id: "a" }), /self_link/);
  // @ts-expect-error invalid kind
  assert.throws(() => validateLinkInput("a", { kind: "bogus", target_task_id: "b" }), /invalid_link_kind/);
  assert.throws(
    () => validateLinkInput("a", { kind: "blocks", target_task_id: "" }),
    /invalid_link_target/,
  );
});

test("addLink writes link on source and inverse on target (blocks ↔ depends_on)", () => {
  const root = mkRoot();
  createTask(root, { slug: "a", title: "A" });
  createTask(root, { slug: "b", title: "B" });
  addLink(root, "a", "blocks", "b");
  const aLinks = readTaskLinks(root, "a");
  const bLinks = readTaskLinks(root, "b");
  assert.deepEqual(aLinks, [{ kind: "blocks", target_task_id: "b" }]);
  assert.deepEqual(bLinks, [{ kind: "depends_on", target_task_id: "a" }]);
  const events = readEvents(root).filter((e) => e.type === "task_linked");
  assert.equal(events.length, 2);
});

test("addLink is idempotent — re-adding emits no extra events", () => {
  const root = mkRoot();
  createTask(root, { slug: "a", title: "A" });
  createTask(root, { slug: "b", title: "B" });
  addLink(root, "a", "blocks", "b");
  const before = readEvents(root).length;
  addLink(root, "a", "blocks", "b");
  const after = readEvents(root).length;
  assert.equal(after, before);
});

test("addLink reflexive for duplicates: A duplicates B writes both A→B and B→A as duplicates", () => {
  const root = mkRoot();
  createTask(root, { slug: "a", title: "A" });
  createTask(root, { slug: "b", title: "B" });
  addLink(root, "a", "duplicates", "b");
  assert.deepEqual(readTaskLinks(root, "a"), [{ kind: "duplicates", target_task_id: "b" }]);
  assert.deepEqual(readTaskLinks(root, "b"), [{ kind: "duplicates", target_task_id: "a" }]);
});

test("addLink subtask_of is one-way: only writes on source", () => {
  const root = mkRoot();
  createTask(root, { slug: "child", title: "child" });
  createTask(root, { slug: "parent", title: "parent" });
  addLink(root, "child", "subtask_of", "parent");
  assert.deepEqual(readTaskLinks(root, "child"), [{ kind: "subtask_of", target_task_id: "parent" }]);
  assert.deepEqual(readTaskLinks(root, "parent"), []);
});

test("addLink throws unknown_task when target doesn't exist", () => {
  const root = mkRoot();
  createTask(root, { slug: "a", title: "A" });
  assert.throws(() => addLink(root, "a", "blocks", "ghost"), /unknown_task/);
});

test("removeLink removes both sides", () => {
  const root = mkRoot();
  createTask(root, { slug: "a", title: "A" });
  createTask(root, { slug: "b", title: "B" });
  addLink(root, "a", "blocks", "b");
  removeLink(root, "a", "blocks", "b");
  assert.deepEqual(readTaskLinks(root, "a"), []);
  assert.deepEqual(readTaskLinks(root, "b"), []);
  const unlinked = readEvents(root).filter((e) => e.type === "task_unlinked");
  assert.equal(unlinked.length, 2);
});

test("links round-trip through frontmatter parse/serialize", () => {
  const links: TaskLink[] = [
    { kind: "blocks", target_task_id: "task-x" },
    { kind: "relates_to", target_task_id: "task-y" },
  ];
  const raw = serializeFrontmatter({ id: "t1", title: "T1", links }, "# body\n");
  const { fm } = parseFrontmatter(raw);
  assert.deepEqual(fm.links, links);
});

test("readTask after addLink reflects link in frontmatter", () => {
  const root = mkRoot();
  createTask(root, { slug: "a", title: "A" });
  createTask(root, { slug: "b", title: "B" });
  addLink(root, "a", "relates_to", "b");
  const t = readTask(root, "a");
  assert.deepEqual(t?.frontmatter.links, [{ kind: "relates_to", target_task_id: "b" }]);
});
