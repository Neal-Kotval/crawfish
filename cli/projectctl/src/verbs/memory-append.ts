import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { redact } from "../redact.js";

export function memoryAppend(repoRoot: string, text: string, userPatterns: RegExp[]): void {
  const path = join(repoRoot, ".crawfish", "memory.md");
  const existing = existsSync(path) ? readFileSync(path, "utf8") : "# Memory\n\n";
  const clean = redact(text, userPatterns);
  if (existing.includes(clean)) return;
  const ts = new Date().toISOString().slice(0, 10);
  writeFileSync(path, existing + `\n- _${ts}_ ${clean}\n`);
}
