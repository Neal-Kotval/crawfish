import { readFileSync, writeFileSync, existsSync, unlinkSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";

export interface Lock {
  release: () => void;
}

function lockPath(repoRoot: string): string {
  return join(repoRoot, ".crawfish", ".lock");
}

export function acquireLock(repoRoot: string, debounceMs: number): Lock | null {
  const path = lockPath(repoRoot);
  mkdirSync(dirname(path), { recursive: true });
  if (existsSync(path)) {
    try {
      const raw = readFileSync(path, "utf8");
      const { ts } = JSON.parse(raw) as { ts: number };
      const ageMs = Date.now() - ts;
      if (ageMs < debounceMs) return null;
    } catch {
      // corrupt lock — overwrite
    }
  }
  writeFileSync(path, JSON.stringify({ ts: Date.now(), pid: process.pid }));
  return {
    release() {
      try { unlinkSync(path); } catch { /* already gone */ }
    },
  };
}
