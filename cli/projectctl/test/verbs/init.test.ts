import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { init } from "../../src/verbs/init.js";

test("creates .crawfish/ on first run", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  const result = init(dir);
  assert.equal(result, "created");
  assert.ok(existsSync(join(dir, ".crawfish/index.json")));
  assert.ok(existsSync(join(dir, ".crawfish/memory.md")));
  assert.ok(existsSync(join(dir, ".crawfish/roadmap.md")));
});

test("is idempotent — second run reports existed", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  init(dir);
  const result = init(dir);
  assert.equal(result, "existed");
});
