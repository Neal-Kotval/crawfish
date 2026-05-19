import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { boardRebuild } from "../src/verbs/board-rebuild.js";
import { readEvents } from "../src/project-board.js";
import { serializeFrontmatter } from "../src/frontmatter.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-rebuild-"));
}

function seedTask(root: string, slug: string, fm: Record<string, unknown>): void {
  const dir = join(root, ".crawfish", "tasks");
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${slug}.md`), serializeFrontmatter(fm as Record<string, string | string[] | number>, `# ${slug}\n`));
}

function seedCycle(root: string, id: string, body: Record<string, unknown>): void {
  const dir = join(root, ".crawfish", "cycles");
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${id}.json`), JSON.stringify(body));
}

test("rebuild on empty project writes no events", () => {
  const root = mkRoot();
  const r = boardRebuild(root);
  assert.equal(r.events_written, 0);
  assert.equal(r.tasks_seen, 0);
  assert.equal(r.cycles_seen, 0);
  assert.deepEqual(readEvents(root), []);
});

test("rebuild emits task_created for each .md file", () => {
  const root = mkRoot();
  seedTask(root, "alpha", { id: "alpha", title: "Alpha", status: "todo", estimate: 1000 });
  seedTask(root, "beta", { id: "beta", title: "Beta", status: "doing" });
  const r = boardRebuild(root);
  assert.equal(r.tasks_seen, 2);
  assert.equal(r.events_written, 2);
  const events = readEvents(root);
  assert.deepEqual(events.map((e) => e.type), ["task_created", "task_created"]);
});

test("rebuild emits cycle_created before tasks reference cycles", () => {
  const root = mkRoot();
  seedCycle(root, "cyc_X", {
    id: "cyc_X",
    name: "X",
    start: "2026-05-18",
    end: "2026-05-25",
    token_budget: 10000,
    status: "open",
    created_at: "2026-05-18T00:00:00Z",
  });
  seedTask(root, "t1", { id: "t1", title: "T1", status: "todo", cycle: "cyc_X" });
  const r = boardRebuild(root);
  assert.equal(r.cycles_seen, 1);
  assert.equal(r.tasks_seen, 1);
  const events = readEvents(root);
  assert.deepEqual(
    events.map((e) => e.type),
    ["cycle_created", "task_created", "task_added_to_cycle"],
  );
  assert.equal(events[0].cycle_id, "cyc_X");
});

test("rebuild is idempotent — running twice produces same output", () => {
  const root = mkRoot();
  seedTask(root, "t1", { id: "t1", title: "T1", status: "todo" });
  boardRebuild(root);
  const first = readEvents(root);
  boardRebuild(root);
  const second = readEvents(root);
  assert.deepEqual(first.map((e) => e.type), second.map((e) => e.type));
  assert.equal(first.length, second.length);
});

test("rebuild atomically replaces existing journal", () => {
  const root = mkRoot();
  // Seed an existing (stale) journal
  mkdirSync(join(root, ".crawfish"), { recursive: true });
  writeFileSync(join(root, ".crawfish", "board.jsonl"), JSON.stringify({ ts: "x", actor: "x", type: "task_created", task_id: "ghost" }) + "\n");
  seedTask(root, "real", { id: "real", title: "Real", status: "todo" });
  boardRebuild(root);
  const events = readEvents(root);
  assert.equal(events.length, 1);
  assert.equal(events[0].task_id, "real");
});

test("rebuild closed cycles emit cycle_closed", () => {
  const root = mkRoot();
  seedCycle(root, "cyc_done", {
    id: "cyc_done",
    name: "Done",
    start: "2026-04-01",
    end: "2026-04-07",
    token_budget: 1000,
    status: "closed",
    created_at: "2026-04-01T00:00:00Z",
  });
  boardRebuild(root);
  const events = readEvents(root);
  assert.deepEqual(events.map((e) => e.type), ["cycle_created", "cycle_closed"]);
});
