import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { memoryAppend } from "../../src/verbs/memory-append.js";

test("appends a memory entry and dedupes identical ones", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  writeFileSync(join(dir, ".crawfish/memory.md"), "# Memory\n\n");
  memoryAppend(dir, "user prefers Postgres", []);
  memoryAppend(dir, "user prefers Postgres", []);
  const got = readFileSync(join(dir, ".crawfish/memory.md"), "utf8");
  const matches = got.match(/user prefers Postgres/g) ?? [];
  assert.equal(matches.length, 1);
});
