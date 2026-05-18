import { z } from "zod";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";

export const SCHEMA_VERSION = "crawfish-project/v1";

const FileEntry = z.object({
  sources: z.array(z.string()),
  hash: z.string().optional(),
  enabled: z.boolean().default(true),
});

const Manifest = z.object({
  schema: z.literal(SCHEMA_VERSION),
  files: z.record(FileEntry),
  last_updated: z.string().optional(),
});

export type Manifest = z.infer<typeof Manifest>;
export type FileEntry = z.infer<typeof FileEntry>;

export const DEFAULT_MANIFEST: Manifest = {
  schema: SCHEMA_VERSION,
  files: {
    "memory.md": { sources: ["~/.claude/projects/**/memory/**/*.md"], enabled: true },
    "context.md": { sources: ["~/.claude/projects/**/sessions/**/*.jsonl"], enabled: true },
    "roadmap.md": { sources: [".planning/**/PLAN.md", ".planning/**/ROADMAP.md", "ROADMAP.md"], enabled: true },
    "decisions.md": { sources: [], enabled: true },
    "activity.md": { sources: [], enabled: false },
  },
};

function manifestPath(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "index.json");
}

export function readManifest(repoRoot: string): Manifest {
  const raw = readFileSync(manifestPath(repoRoot), "utf8");
  const parsed = JSON.parse(raw);
  return Manifest.parse(parsed);
}

export function writeManifest(repoRoot: string, manifest: Manifest): void {
  const path = manifestPath(repoRoot);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(manifest, null, 2) + "\n");
}
