import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderContext } from "../../src/renderers/context.js";

test("summarizes session files by count and size", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "a.jsonl"), "x".repeat(100));
  writeFileSync(join(dir, "b.jsonl"), "y".repeat(50));
  const md = await renderContext("/unused", [join(dir, "*.jsonl")]);
  assert.match(md, /2 sessions/);
  assert.match(md, /150 B|150 bytes/);
});

test("empty state when no sessions match", async () => {
  const md = await renderContext("/unused", ["/nonexistent/*.jsonl"]);
  assert.match(md, /no sessions/i);
});
