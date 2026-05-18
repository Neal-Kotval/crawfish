import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { init } from "../../src/verbs/init.js";

process.env.CRAWFISH_SKIP_DASH_REGISTER = "1";

test("creates .crawfish/ on first run", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  const result = await init(dir);
  assert.equal(result, "created");
  assert.ok(existsSync(join(dir, ".crawfish/index.json")));
  assert.ok(existsSync(join(dir, ".crawfish/memory.md")));
  assert.ok(existsSync(join(dir, ".crawfish/roadmap.md")));
});

test("is idempotent — second run reports existed", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  await init(dir);
  const result = await init(dir);
  assert.equal(result, "existed");
});
