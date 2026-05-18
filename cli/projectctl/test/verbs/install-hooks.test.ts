import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { installHooks, uninstallHooks } from "../../src/verbs/install-hooks.js";

test("creates .claude/settings.json with three crawfish hooks", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  installHooks(dir);
  const settings = JSON.parse(readFileSync(join(dir, ".claude/settings.json"), "utf8"));
  assert.ok(settings.hooks.SessionEnd.some((h: any) => h._crawfish));
  assert.ok(settings.hooks.PostToolUse.some((h: any) => h._crawfish));
  assert.ok(settings.hooks.UserPromptSubmit.some((h: any) => h._crawfish));
});

test("uninstall removes only crawfish-tagged hooks", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".claude"));
  writeFileSync(join(dir, ".claude/settings.json"), JSON.stringify({
    hooks: { SessionEnd: [{ command: "echo user-hook" }] },
  }));
  installHooks(dir);
  uninstallHooks(dir);
  const settings = JSON.parse(readFileSync(join(dir, ".claude/settings.json"), "utf8"));
  assert.equal(settings.hooks.SessionEnd.length, 1);
  assert.equal(settings.hooks.SessionEnd[0].command, "echo user-hook");
});
