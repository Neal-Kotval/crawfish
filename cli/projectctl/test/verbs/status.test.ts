import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { init } from "../../src/verbs/init.js";
import { refresh } from "../../src/verbs/refresh.js";
import { status } from "../../src/verbs/status.js";
import { doctor } from "../../src/verbs/doctor.js";

test("status reports stale files after a source change", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "ROADMAP.md"), "# v1");
  init(dir);
  await refresh(dir, { debounceMs: 0 });
  writeFileSync(join(dir, "ROADMAP.md"), "# v2");
  const s = await status(dir);
  assert.ok(s.stale.includes("roadmap.md"));
});

test("doctor flags an unknown schema version", () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  init(dir);
  writeFileSync(join(dir, ".crawfish/index.json"), JSON.stringify({ schema: "crawfish-project/v999", files: {} }));
  const d = doctor(dir);
  assert.ok(d.errors.some((e) => /schema/.test(e)));
});
