import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { createTask, updateTask, readTask } from "../src/tasks.js";
import { readEvents } from "../src/project-board.js";
import {
  parseFrontmatter,
  serializeFrontmatter,
  type Criterion,
} from "../src/frontmatter.js";

function mkRoot(): string {
  return mkdtempSync(join(tmpdir(), "cfp-criteria-"));
}

const C1: Criterion = { id: "c1", statement: "must do X", kind: "test" };
const C2: Criterion = { id: "c2", statement: "must do Y", kind: "manual" };

test("criteria round-trip through serialize → parse → serialize", () => {
  const fm = {
    id: "t1",
    title: "T1",
    status: "todo",
    criteria: [
      { id: "c1", statement: "rejects stale If-Match", kind: "test" as const,
        evidence: { kind: "test" as const, path: "test/foo.test.ts", testCase: "rejects stale" } },
      { id: "c2", statement: "operator sign-off", kind: "manual" as const },
    ],
  };
  const raw = serializeFrontmatter(fm, "# body\n");
  const parsed = parseFrontmatter(raw);
  assert.equal(Array.isArray(parsed.fm.criteria), true);
  const crits = parsed.fm.criteria as Criterion[];
  assert.equal(crits.length, 2);
  assert.equal(crits[0].id, "c1");
  assert.equal(crits[0].kind, "test");
  assert.equal(crits[0].statement, "rejects stale If-Match");
  assert.ok(crits[0].evidence);
  assert.equal(crits[0].evidence?.kind, "test");
  assert.equal(crits[0].evidence?.path, "test/foo.test.ts");
  assert.equal(crits[0].evidence?.testCase, "rejects stale");
  assert.equal(crits[1].id, "c2");
  assert.equal(crits[1].evidence, undefined);

  // Second round trip is stable.
  const raw2 = serializeFrontmatter(parsed.fm, parsed.body);
  const parsed2 = parseFrontmatter(raw2);
  assert.deepEqual(parsed2.fm.criteria, parsed.fm.criteria);
});

test("criteria persist through createTask → readTask", () => {
  const root = mkRoot();
  createTask(root, {
    slug: "t1",
    title: "T1",
    criteria: [C1, C2],
  });
  const t = readTask(root, "t1");
  const crits = t?.frontmatter.criteria as Criterion[];
  assert.equal(crits.length, 2);
  assert.equal(crits[0].id, "c1");
  assert.equal(crits[1].id, "c2");
});

test("updateTask criteria replaces array and emits criterion_set", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1" });
  updateTask(root, "t1", { criteria: [C1, C2] });
  const t = readTask(root, "t1");
  assert.equal((t?.frontmatter.criteria as Criterion[]).length, 2);

  const events = readEvents(root);
  const setEv = events.find((e) => e.type === "criterion_set");
  assert.ok(setEv);
  const payload = setEv?.payload as { criteria: Criterion[] };
  assert.equal(payload.criteria.length, 2);

  // Replace with single criterion.
  updateTask(root, "t1", { criteria: [C1] });
  const t2 = readTask(root, "t1");
  assert.equal((t2?.frontmatter.criteria as Criterion[]).length, 1);
});

test("updateTask setCriterionEvidence stores evidence and emits criterion_met", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", criteria: [C1] });
  updateTask(root, "t1", {
    setCriterionEvidence: {
      id: "c1",
      evidence: { kind: "test", path: "test/x.test.ts", testCase: "X" },
    },
  });
  const t = readTask(root, "t1");
  const crit = (t?.frontmatter.criteria as Criterion[])[0];
  assert.ok(crit.evidence);
  assert.equal(crit.evidence?.path, "test/x.test.ts");

  const events = readEvents(root);
  const met = events.find((e) => e.type === "criterion_met");
  assert.ok(met);
  const payload = met?.payload as { id: string; kind: string; evidence: Record<string, unknown> };
  assert.equal(payload.id, "c1");
  assert.equal(payload.kind, "test");
  assert.equal(payload.evidence.path, "test/x.test.ts");
});

test("updateTask clearCriterionEvidence removes evidence and emits criterion_cleared", () => {
  const root = mkRoot();
  createTask(root, {
    slug: "t1",
    title: "T1",
    criteria: [{ ...C1, evidence: { kind: "test", path: "p" } }],
  });
  updateTask(root, "t1", { clearCriterionEvidence: { id: "c1", by: "alice" } });
  const t = readTask(root, "t1");
  const crit = (t?.frontmatter.criteria as Criterion[])[0];
  assert.equal(crit.evidence, undefined);

  const events = readEvents(root);
  const cleared = events.find((e) => e.type === "criterion_cleared");
  assert.ok(cleared);
  const payload = cleared?.payload as { id: string; by: string };
  assert.equal(payload.id, "c1");
  assert.equal(payload.by, "alice");
});

test("unknown criterion id throws unknown_criterion", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", criteria: [C1] });
  assert.throws(
    () => updateTask(root, "t1", {
      setCriterionEvidence: { id: "nope", evidence: { kind: "test" } },
    }),
    /unknown_criterion/,
  );
  assert.throws(
    () => updateTask(root, "t1", {
      clearCriterionEvidence: { id: "nope", by: "alice" },
    }),
    /unknown_criterion/,
  );
});

test("done transition blocked when any criterion lacks evidence", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", criteria: [C1, C2] });
  let caught: Error | null = null;
  try {
    updateTask(root, "t1", { status: "done" });
  } catch (e) {
    caught = e as Error;
  }
  assert.ok(caught);
  assert.match(caught!.message, /^criteria_unmet:/);
  const jsonPart = caught!.message.slice("criteria_unmet:".length).trim();
  const parsed = JSON.parse(jsonPart) as { code: string; task_id: string; unmet: string[] };
  assert.equal(parsed.code, "criteria_unmet");
  assert.equal(parsed.task_id, "t1");
  assert.deepEqual(parsed.unmet.sort(), ["c1", "c2"]);

  // Task must not have transitioned.
  const t = readTask(root, "t1");
  assert.equal(t?.frontmatter.status, "todo");
});

test("done transition allowed when all criteria have evidence", () => {
  const root = mkRoot();
  createTask(root, {
    slug: "t1",
    title: "T1",
    criteria: [
      { ...C1, evidence: { kind: "test", path: "p" } },
      { ...C2, evidence: { kind: "manual", by: "alice", at: "2026-05-19T00:00:00Z" } },
    ],
  });
  updateTask(root, "t1", { status: "done" });
  const t = readTask(root, "t1");
  assert.equal(t?.frontmatter.status, "done");
});

test("done transition allowed when criteria is empty (back-compat)", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1" });
  updateTask(root, "t1", { status: "done" });
  const t = readTask(root, "t1");
  assert.equal(t?.frontmatter.status, "done");
});

test("setting evidence and transitioning to done in the same patch is allowed", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", criteria: [C1] });
  updateTask(root, "t1", {
    setCriterionEvidence: { id: "c1", evidence: { kind: "test", path: "p" } },
    status: "done",
  });
  const t = readTask(root, "t1");
  assert.equal(t?.frontmatter.status, "done");
  const crit = (t?.frontmatter.criteria as Criterion[])[0];
  assert.ok(crit.evidence);
});

test("criteria array via patch + done in same patch (replaces unmet with met)", () => {
  const root = mkRoot();
  createTask(root, { slug: "t1", title: "T1", criteria: [C1] });
  updateTask(root, "t1", {
    criteria: [{ ...C1, evidence: { kind: "test", path: "p" } }],
    status: "done",
  });
  const t = readTask(root, "t1");
  assert.equal(t?.frontmatter.status, "done");
});
