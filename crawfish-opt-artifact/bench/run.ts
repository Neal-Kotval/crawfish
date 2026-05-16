// Benchmark — five large fixtures put through artifact_put. Asserts the
// returned envelope is ≥10× smaller than the naive return.

import { putArtifact } from "../src/store.js";
import { approxTokens } from "../src/tokens.js";

interface Fixture {
  name: string;
  payload: string;
}

function repeat(line: string, n: number): string {
  return new Array(n).fill(line).join("\n");
}

const FIXTURES: Fixture[] = [
  {
    name: "html-dump",
    payload: "<html><body>" + repeat("<div>row</div>", 2000) + "</body></html>",
  },
  {
    name: "json-api",
    payload: JSON.stringify(
      Array.from({ length: 500 }, (_, i) => ({
        id: i,
        title: `Item ${i}`,
        body: "lorem ipsum dolor sit amet ".repeat(20),
        created_at: "2026-05-16T00:00:00Z",
      })),
    ),
  },
  {
    name: "log-tail",
    payload: repeat("2026-05-16T12:34:56Z INFO worker processed 1 task", 4000),
  },
  {
    name: "csv-dump",
    payload:
      "id,name,email,created_at\n" +
      repeat("123,Test User,test@example.com,2026-05-16T00:00:00Z", 3000),
  },
  {
    name: "stacktrace-megadump",
    payload:
      "Exception: x\n" +
      repeat("    at com.example.Class.method(File.java:42)", 500),
  },
];

const REQUIRED = 10;
let failed = 0;
const rows: Array<{
  fixture: string;
  naive: number;
  envelope: number;
  reduction: string;
}> = [];

for (const f of FIXTURES) {
  const naive = approxTokens(f.payload);
  const env = putArtifact(f.payload, { source_tool: "bench" });
  const envTokens = approxTokens(JSON.stringify(env));
  const ratio = naive / Math.max(1, envTokens);
  rows.push({
    fixture: f.name,
    naive,
    envelope: envTokens,
    reduction: ratio.toFixed(1) + "×",
  });
  if (ratio < REQUIRED) {
    console.error(`FAIL  ${f.name}: ${ratio.toFixed(1)}× < ${REQUIRED}×`);
    failed++;
  }
}

console.log("");
console.log("  fixture                  naive    envelope  reduction");
console.log("  ───────────────────────  ───────  ────────  ─────────");
for (const r of rows) {
  console.log(
    `  ${r.fixture.padEnd(23)}  ${String(r.naive).padStart(7)}  ${String(r.envelope).padStart(8)}  ${r.reduction.padStart(9)}`,
  );
}

const avg =
  rows.reduce((a, r) => a + r.naive / Math.max(1, r.envelope), 0) / rows.length;
console.log(`\n  Average reduction: ${avg.toFixed(1)}×`);

if (failed > 0) {
  console.error(`\n${failed} fixture(s) failed`);
  process.exit(1);
}
console.log("\nAll fixtures green.");
