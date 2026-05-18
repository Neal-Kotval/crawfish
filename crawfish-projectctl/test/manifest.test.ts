// test/manifest.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readManifest, writeManifest, DEFAULT_MANIFEST } from "../src/manifest.js";

test("reads a manifest written to disk", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeManifest(dir, DEFAULT_MANIFEST);
  const got = readManifest(dir);
  assert.equal(got.schema, "crawfish-project/v1");
  assert.ok(got.files["roadmap.md"]);
});

test("rejects manifests with the wrong schema version", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"), { recursive: true });
  writeFileSync(join(dir, ".crawfish", "index.json"), JSON.stringify({ schema: "crawfish-project/v999", files: {} }));
  assert.throws(() => readManifest(dir), /schema/);
});
