import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { dispatch } from "../../src/mcp/server.js";

test("project_refresh tool runs refresh", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "ROADMAP.md"), "# v1");
  await dispatch("project_init", { repo_root: dir });
  const res = await dispatch("project_refresh", { repo_root: dir });
  assert.ok(Array.isArray(res.refreshed));
});

test("project_decision_add appends to decisions.md", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  await dispatch("project_init", { repo_root: dir });
  await dispatch("project_decision_add", { repo_root: dir, title: "T", body: "B" });
  const got = readFileSync(join(dir, ".crawfish/decisions.md"), "utf8");
  assert.match(got, /## T/);
});
