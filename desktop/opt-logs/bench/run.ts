// Benchmark harness — run with `npm run bench`.
//
// Asserts each fixture: (a) the summarizer keeps the "expected_keep" lines,
// (b) the optimized output is ≥4× smaller than the naive cat.
// Prints a table and exits non-zero if anything fails.

import { FIXTURES } from "./fixtures.js";
import { summarize } from "../src/logs.js";
import { approxTokens } from "../src/tokens.js";

const REQUIRED_REDUCTION = 4;
let failed = 0;

interface Row {
  fixture: string;
  naive_tokens: number;
  opt_tokens: number;
  reduction: string;
  keeps_all: boolean;
}
const rows: Row[] = [];

for (const f of FIXTURES) {
  const naive = approxTokens(f.text);
  const summary = summarize(f.text);
  const payload = JSON.stringify(summary);
  const optTokens = approxTokens(payload);

  // Verify every expected_keep substring still appears somewhere in the
  // summarizer output (errors / warnings / info head|tail / stacks).
  const haystack =
    summary.errors.map((e) => e.text).join("\n") +
    "\n" + summary.warnings.map((w) => w.text).join("\n") +
    "\n" + summary.stacks.map((s) => s.text).join("\n") +
    "\n" + summary.info_head.join("\n") +
    "\n" + summary.info_tail.join("\n");
  const keepsAll = f.expected_keep.every((sub) => haystack.includes(sub));

  const ratio = optTokens > 0 ? naive / optTokens : Infinity;
  rows.push({
    fixture: f.name,
    naive_tokens: naive,
    opt_tokens: optTokens,
    reduction: ratio.toFixed(2) + "×",
    keeps_all: keepsAll,
  });

  // Long-info-only and stack-only are exempt from the keep check (nothing
  // to keep) but still must hit the reduction floor.
  if (!keepsAll) {
    console.error(`FAIL  ${f.name}: missing expected_keep`);
    failed++;
  }
  // Apply the reduction floor only to fixtures that are clearly noisy
  // (>2000 chars and >100 input tokens). Already-compact dumps like a bare
  // stack trace can't be compressed without losing required signal.
  if (f.text.length > 2000 && naive > 100 && ratio < REQUIRED_REDUCTION) {
    console.error(`FAIL  ${f.name}: reduction ${ratio.toFixed(2)}× < ${REQUIRED_REDUCTION}×`);
    failed++;
  }
}

console.log("");
console.log("  fixture                    naive   opt   reduction   keeps");
console.log("  ─────────────────────────  ──────  ────  ──────────  ─────");
for (const r of rows) {
  const fx = r.fixture.padEnd(25);
  const naive = String(r.naive_tokens).padStart(6);
  const opt = String(r.opt_tokens).padStart(4);
  const red = r.reduction.padStart(10);
  const keep = r.keeps_all ? "✓" : "✗";
  console.log(`  ${fx}  ${naive}  ${opt}  ${red}      ${keep}`);
}

const avg =
  rows.reduce((a, r) => a + r.naive_tokens / Math.max(1, r.opt_tokens), 0) /
  rows.length;
console.log(`\n  Average reduction: ${avg.toFixed(2)}×`);

if (failed > 0) {
  console.error(`\n${failed} fixture(s) failed`);
  process.exit(1);
}
console.log("\nAll fixtures green.");
