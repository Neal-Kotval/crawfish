import { readManifest } from "../manifest.js";
import { hashSources } from "../hash.js";

export async function status(repoRoot: string): Promise<{ stale: string[]; fresh: string[] }> {
  const manifest = readManifest(repoRoot);
  const stale: string[] = [];
  const fresh: string[] = [];
  for (const [filename, entry] of Object.entries(manifest.files)) {
    if (!entry.enabled) continue;
    const h = await hashSources(repoRoot, entry.sources);
    if (h === entry.hash) fresh.push(filename);
    else stale.push(filename);
  }
  return { stale, fresh };
}
