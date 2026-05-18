import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { init } from "../../src/verbs/init.js";
import { refresh } from "../../src/verbs/refresh.js";

test("re-renders roadmap.md when ROADMAP.md changes", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "ROADMAP.md"), "# Roadmap v1\n\nA");
  init(dir);
  const r1 = await refresh(dir, { debounceMs: 0 });
  assert.ok(r1.refreshed.includes("roadmap.md"));
  const md1 = readFileSync(join(dir, ".crawfish/roadmap.md"), "utf8");
  assert.match(md1, /Roadmap v1/);

  // Second refresh with no source change should skip
  const r2 = await refresh(dir, { debounceMs: 0 });
  assert.equal(r2.refreshed.length, 0);
  assert.ok(r2.skipped.includes("roadmap.md"));

  // Change source, refresh again
  writeFileSync(join(dir, "ROADMAP.md"), "# Roadmap v2\n\nB");
  const r3 = await refresh(dir, { debounceMs: 0 });
  assert.ok(r3.refreshed.includes("roadmap.md"));
  const md3 = readFileSync(join(dir, ".crawfish/roadmap.md"), "utf8");
  assert.match(md3, /Roadmap v2/);
});

test("debounce returns early when lock is fresh", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  init(dir);
  await refresh(dir, { debounceMs: 60_000 });
  const r2 = await refresh(dir, { debounceMs: 60_000 });
  assert.equal(r2.debounced, true);
});
