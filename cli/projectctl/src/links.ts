/**
 * Task-link helpers — five link kinds plus reciprocal-edge auto-management.
 *
 * Five recognized kinds:
 *   - blocks       (inverse of depends_on)
 *   - depends_on   (inverse of blocks)
 *   - duplicates   (reflexive: A duplicates B ⇒ B duplicates A)
 *   - relates_to   (reflexive)
 *   - subtask_of   (one-way; spec lists no `parent_of` kind, so no inverse)
 *
 * All mutations route through `updateTask` so the single-writer invariant
 * (see ADR-001) holds and `task_linked`/`task_unlinked` events land on
 * `.crawfish/board.jsonl`.
 */
import { existsSync } from "node:fs";
import { join } from "node:path";

import { readTask, updateTask, readTaskLinks } from "./tasks.js";
import { LINK_KINDS, type LinkKind, type TaskLink } from "./frontmatter.js";

/**
 * Returns the inverse kind to write on the *target* task, or null if the
 * relation is one-way. `duplicates` and `relates_to` are reflexive, so they
 * return themselves.
 */
export function reciprocalKind(kind: LinkKind): LinkKind | null {
  switch (kind) {
    case "blocks":
      return "depends_on";
    case "depends_on":
      return "blocks";
    case "duplicates":
      return "duplicates";
    case "relates_to":
      return "relates_to";
    case "subtask_of":
      return null;
  }
}

export interface LinkInput {
  kind: LinkKind;
  target_task_id: string;
}

export function validateLinkInput(sourceSlug: string, input: LinkInput): void {
  if (!LINK_KINDS.includes(input.kind)) {
    throw new Error(`invalid_link_kind: ${input.kind}`);
  }
  if (!input.target_task_id || typeof input.target_task_id !== "string") {
    throw new Error(`invalid_link_target: ${String(input.target_task_id)}`);
  }
  if (sourceSlug === input.target_task_id) {
    throw new Error(`self_link: ${sourceSlug}`);
  }
}

function assertTaskExists(repoRoot: string, slug: string): void {
  const path = join(repoRoot, ".crawfish", "tasks", `${slug}.md`);
  if (!existsSync(path)) throw new Error(`unknown_task: ${slug}`);
}

function hasLink(links: TaskLink[], kind: LinkKind, target: string): boolean {
  return links.some((l) => l.kind === kind && l.target_task_id === target);
}

export interface LinkOptions {
  actor?: string;
}

/**
 * Add a link from `sourceSlug` to `targetSlug`. Also writes the reciprocal
 * edge on the target when the kind has an inverse or is reflexive.
 *
 * Idempotent: re-adding an existing link is a no-op.
 */
export function addLink(
  repoRoot: string,
  sourceSlug: string,
  kind: LinkKind,
  targetSlug: string,
  opts: LinkOptions = {},
): void {
  validateLinkInput(sourceSlug, { kind, target_task_id: targetSlug });
  assertTaskExists(repoRoot, sourceSlug);
  assertTaskExists(repoRoot, targetSlug);

  const sourceLinks = readTaskLinks(repoRoot, sourceSlug);
  if (!hasLink(sourceLinks, kind, targetSlug)) {
    const next = [...sourceLinks, { kind, target_task_id: targetSlug }];
    updateTask(repoRoot, sourceSlug, { links: next, actor: opts.actor });
  }

  const inverse = reciprocalKind(kind);
  if (inverse) {
    const targetLinks = readTaskLinks(repoRoot, targetSlug);
    if (!hasLink(targetLinks, inverse, sourceSlug)) {
      const next = [...targetLinks, { kind: inverse, target_task_id: sourceSlug }];
      updateTask(repoRoot, targetSlug, { links: next, actor: opts.actor });
    }
  }
}

/**
 * Remove a link from `sourceSlug` to `targetSlug`. Removes the reciprocal
 * edge if it exists. Idempotent.
 */
export function removeLink(
  repoRoot: string,
  sourceSlug: string,
  kind: LinkKind,
  targetSlug: string,
  opts: LinkOptions = {},
): void {
  validateLinkInput(sourceSlug, { kind, target_task_id: targetSlug });
  if (!readTask(repoRoot, sourceSlug)) throw new Error(`unknown_task: ${sourceSlug}`);

  const sourceLinks = readTaskLinks(repoRoot, sourceSlug);
  if (hasLink(sourceLinks, kind, targetSlug)) {
    const next = sourceLinks.filter(
      (l) => !(l.kind === kind && l.target_task_id === targetSlug),
    );
    updateTask(repoRoot, sourceSlug, { links: next, actor: opts.actor });
  }

  const inverse = reciprocalKind(kind);
  if (inverse) {
    const targetTask = readTask(repoRoot, targetSlug);
    if (targetTask) {
      const targetLinks = readTaskLinks(repoRoot, targetSlug);
      if (hasLink(targetLinks, inverse, sourceSlug)) {
        const next = targetLinks.filter(
          (l) => !(l.kind === inverse && l.target_task_id === sourceSlug),
        );
        updateTask(repoRoot, targetSlug, { links: next, actor: opts.actor });
      }
    }
  }
}
