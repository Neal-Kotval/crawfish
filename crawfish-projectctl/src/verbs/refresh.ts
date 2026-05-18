import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { readManifest, writeManifest } from "../manifest.js";
import { hashSources } from "../hash.js";
import { acquireLock } from "../lock.js";
import { renderRoadmap } from "../renderers/roadmap.js";
import { renderMemory } from "../renderers/memory.js";
import { renderContext } from "../renderers/context.js";

export interface RefreshOptions {
  debounceMs?: number;
  only?: string[];
  userRedactPatterns?: RegExp[];
}

export interface RefreshResult {
  refreshed: string[];
  skipped: string[];
  debounced?: boolean;
}

type Renderer = (repoRoot: string, sources: string[], userPatterns: RegExp[]) => Promise<string>;

const RENDERERS: Record<string, Renderer> = {
  "roadmap.md": (root, sources) => renderRoadmap(root, sources),
  "memory.md": (root, sources, patterns) => renderMemory(root, sources, patterns),
  "context.md": (root, sources) => renderContext(root, sources),
};

export async function refresh(repoRoot: string, opts: RefreshOptions = {}): Promise<RefreshResult> {
  const { debounceMs = 0, only, userRedactPatterns = [] } = opts;
  const lock = acquireLock(repoRoot, debounceMs);
  if (!lock) return { refreshed: [], skipped: [], debounced: true };
  try {
    const manifest = readManifest(repoRoot);
    const result: RefreshResult = { refreshed: [], skipped: [] };
    for (const [filename, entry] of Object.entries(manifest.files)) {
      if (!entry.enabled) continue;
      if (only && !only.includes(filename)) continue;
      const renderer = RENDERERS[filename];
      if (!renderer) {
        result.skipped.push(filename);
        continue;
      }
      const newHash = await hashSources(repoRoot, entry.sources);
      if (newHash === entry.hash) {
        result.skipped.push(filename);
        continue;
      }
      const md = await renderer(repoRoot, entry.sources, userRedactPatterns);
      writeFileSync(join(repoRoot, ".crawfish", filename), md);
      manifest.files[filename] = { ...entry, hash: newHash };
      result.refreshed.push(filename);
    }
    manifest.last_updated = new Date().toISOString();
    writeManifest(repoRoot, manifest);
    return result;
  } finally {
    lock.release();
  }
}
