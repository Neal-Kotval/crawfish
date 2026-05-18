// test/integration.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { cpSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { init } from "../src/verbs/init.js";
import { refresh } from "../src/verbs/refresh.js";

process.env.CRAWFISH_SKIP_DASH_REGISTER = "1";

function cloneFixture(name: string): string {
  const src = resolve("fixtures", name);
  const dst = mkdtempSync(join(tmpdir(), `${name}-`));
  cpSync(src, dst, { recursive: true });
  return dst;
}

test("end-to-end: gsd-project produces a multi-phase roadmap.md", async () => {
  const dir = cloneFixture("gsd-project");
  await init(dir);
  await refresh(dir, { debounceMs: 0 });
  const roadmap = readFileSync(join(dir, ".crawfish/roadmap.md"), "utf8");
  assert.match(roadmap, /Phase 1 — Authentication/);
  assert.match(roadmap, /Phase 2 — Project Import/);
});

test("end-to-end: plain-readme-project produces a single-source roadmap.md", async () => {
  const dir = cloneFixture("plain-readme-project");
  await init(dir);
  await refresh(dir, { debounceMs: 0 });
  const roadmap = readFileSync(join(dir, ".crawfish/roadmap.md"), "utf8");
  assert.match(roadmap, /Roadmap/);
  assert.match(roadmap, /Milestone A/);
});
