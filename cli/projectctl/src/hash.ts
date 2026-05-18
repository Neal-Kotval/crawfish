import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { glob } from "glob";
import { homedir } from "node:os";
import { join } from "node:path";

function expandHome(p: string): string {
  return p.startsWith("~/") ? join(homedir(), p.slice(2)) : p;
}

export async function hashSources(repoRoot: string, patterns: string[]): Promise<string> {
  const matched = new Set<string>();
  for (const pattern of patterns) {
    const expanded = expandHome(pattern);
    const cwd = expanded.startsWith("/") ? "/" : repoRoot;
    const rel = expanded.startsWith("/") ? expanded.slice(1) : expanded;
    const files = await glob(rel, { cwd, nodir: true, absolute: true });
    for (const f of files) matched.add(f);
  }
  const sorted = [...matched].sort();
  const h = createHash("sha256");
  for (const path of sorted) {
    const size = statSync(path).size;
    const content = readFileSync(path);
    h.update(path);
    h.update(String(size));
    h.update(content);
    h.update("\x00");
  }
  return "sha256:" + h.digest("hex");
}
