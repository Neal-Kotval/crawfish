import { addLink } from "../links.js";
import type { LinkKind } from "../frontmatter.js";

export function linkAdd(
  repoRoot: string,
  source: string,
  kind: LinkKind,
  target: string,
): void {
  addLink(repoRoot, source, kind, target);
}
