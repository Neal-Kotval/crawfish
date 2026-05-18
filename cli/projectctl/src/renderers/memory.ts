import { glob } from "glob";
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { redact } from "../redact.js";

export async function renderMemory(_repoRoot: string, sources: string[], userRedactPatterns: RegExp[]): Promise<string> {
  const matched = new Set<string>();
  for (const pattern of sources) {
    const files = await glob(pattern, { nodir: true, absolute: true });
    for (const f of files) matched.add(f);
  }
  if (matched.size === 0) {
    return "# Memory\n\n_No project memory found. Auto-memory will populate this on the next session._\n";
  }
  const sorted = [...matched].sort();
  const lines = ["# Memory", ""];
  for (const abs of sorted) {
    const content = readFileSync(abs, "utf8");
    lines.push(`## ${basename(abs)}`);
    lines.push(redact(content, userRedactPatterns));
    lines.push("");
  }
  return lines.join("\n");
}
