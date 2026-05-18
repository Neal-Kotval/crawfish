import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { activityRecord } from "../../src/verbs/activity-record.js";

test("appends a session summary and trims to last N", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  writeFileSync(join(dir, ".crawfish/activity.md"), "# Activity\n\n");
  for (let i = 0; i < 60; i++) {
    activityRecord(dir, `summary ${i}`, 50);
  }
  const got = readFileSync(join(dir, ".crawfish/activity.md"), "utf8");
  const entries = got.match(/^### /gm) ?? [];
  assert.equal(entries.length, 50);
  assert.match(got, /summary 59/);
  assert.doesNotMatch(got, /summary 0\b/);
});
