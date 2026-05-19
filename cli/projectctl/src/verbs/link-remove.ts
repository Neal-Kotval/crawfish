import { removeLink } from "../links.js";
import type { LinkKind } from "../frontmatter.js";

export function linkRemove(
  repoRoot: string,
  source: string,
  kind: LinkKind,
  target: string,
): void {
  removeLink(repoRoot, source, kind, target);
}
