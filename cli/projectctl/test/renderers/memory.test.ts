import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderMemory } from "../../src/renderers/memory.js";

test("concatenates memory files and redacts secrets", async () => {
  const memDir = mkdtempSync(join(tmpdir(), "cfp-mem-"));
  writeFileSync(join(memDir, "feedback.md"), "user prefers terse responses");
  writeFileSync(join(memDir, "leak.md"), "key sk-proj-abcdefghijklmnopqrstuvwx");
  const md = await renderMemory("/unused", [join(memDir, "*.md")], []);
  assert.match(md, /user prefers terse responses/);
  assert.match(md, /\[REDACTED\]/);
  assert.doesNotMatch(md, /sk-proj-abcdef/);
});

test("empty state when no memory exists", async () => {
  const md = await renderMemory("/unused", ["/nonexistent/**/*.md"], []);
  assert.match(md, /no project memory/i);
});
