import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { decisionAdd } from "../../src/verbs/decision-add.js";

test("appends a dated ADR entry to decisions.md", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".crawfish"));
  writeFileSync(join(dir, ".crawfish/decisions.md"), "# Decisions\n\n");
  decisionAdd(dir, "Use Postgres", "Lower ops cost than DynamoDB at our scale.");
  const got = readFileSync(join(dir, ".crawfish/decisions.md"), "utf8");
  assert.match(got, /## Use Postgres/);
  assert.match(got, /Lower ops cost/);
  assert.match(got, /\d{4}-\d{2}-\d{2}/);
});
