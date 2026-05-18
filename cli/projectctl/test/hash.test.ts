import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { hashSources } from "../src/hash.js";

function makeRepo(): string {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".planning"), { recursive: true });
  writeFileSync(join(dir, ".planning", "PLAN.md"), "phase 1");
  writeFileSync(join(dir, "ROADMAP.md"), "milestone A");
  return dir;
}

test("hash is stable across runs for unchanged sources", async () => {
  const dir = makeRepo();
  const h1 = await hashSources(dir, [".planning/**/PLAN.md", "ROADMAP.md"]);
  const h2 = await hashSources(dir, [".planning/**/PLAN.md", "ROADMAP.md"]);
  assert.equal(h1, h2);
});

test("hash changes when a source file changes", async () => {
  const dir = makeRepo();
  const h1 = await hashSources(dir, ["ROADMAP.md"]);
  writeFileSync(join(dir, "ROADMAP.md"), "milestone B");
  const h2 = await hashSources(dir, ["ROADMAP.md"]);
  assert.notEqual(h1, h2);
});

test("hash is independent of glob ordering", async () => {
  const dir = makeRepo();
  const h1 = await hashSources(dir, ["ROADMAP.md", ".planning/**/PLAN.md"]);
  const h2 = await hashSources(dir, [".planning/**/PLAN.md", "ROADMAP.md"]);
  assert.equal(h1, h2);
});
