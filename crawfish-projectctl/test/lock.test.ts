import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { acquireLock } from "../src/lock.js";

test("second acquire within debounce window returns null", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  const first = acquireLock(dir, 60_000);
  assert.ok(first, "first acquire should succeed");
  const second = acquireLock(dir, 60_000);
  assert.equal(second, null, "second acquire inside window should be null");
  first!.release();
});

test("acquire after release works", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  const first = acquireLock(dir, 0);
  first!.release();
  const second = acquireLock(dir, 0);
  assert.ok(second);
  second!.release();
});
