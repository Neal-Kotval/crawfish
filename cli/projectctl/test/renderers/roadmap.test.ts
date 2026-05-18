import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderRoadmap } from "../../src/renderers/roadmap.js";

test("renders headings from .planning/ PLAN.md files", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  mkdirSync(join(dir, ".planning", "P1"), { recursive: true });
  writeFileSync(join(dir, ".planning", "P1", "PLAN.md"), "# Phase 1 — auth\n\nbody");
  const md = await renderRoadmap(dir, [".planning/**/PLAN.md"]);
  assert.match(md, /Phase 1 — auth/);
  assert.match(md, /\.planning\/P1\/PLAN\.md/);
});

test("falls back to a single-source render for a plain ROADMAP.md", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  writeFileSync(join(dir, "ROADMAP.md"), "# Roadmap\n\nMilestone A");
  const md = await renderRoadmap(dir, ["ROADMAP.md"]);
  assert.match(md, /Roadmap/);
});

test("emits a graceful empty state when no sources exist", async () => {
  const dir = mkdtempSync(join(tmpdir(), "cfp-"));
  const md = await renderRoadmap(dir, [".planning/**/PLAN.md"]);
  assert.match(md, /no roadmap sources/i);
});
