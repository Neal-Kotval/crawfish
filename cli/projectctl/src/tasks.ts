/**
 * Single-writer module for project-level Crawfish tasks.
 *
 * Per ADR-001 (Option C), every mutation to `.crawfish/tasks/*.md` MUST go
 * through this module. Each function (a) writes the `.md` file and (b)
 * appends an event to `.crawfish/board.jsonl` in one operation. Direct
 * filesystem writes elsewhere in the codebase are forbidden — see the ADR.
 *
 * Frontmatter fields recognised by Week 1.1:
 *   id           — task ULID (string)
 *   title        — short label, also the H1 in the body if absent
 *   status       — "todo" | "doing" | "done" | "blocked"
 *   phase        — "now" | "next" | "later"        (from ROADMAP.md)
 *   estimate     — token estimate (number)
 *   depends-on   — array of task slugs
 *   cycle        — cycle ULID, if assigned         (Week 1.1)
 *   epic         — epic ULID, if assigned           (Week 1.1)
 *
 * Slug rules: 1–40 chars, [a-z0-9_-], lowercase, kebab-case preferred. Same
 * regex as the dash reader so files written here are visible to ProjectBoard.
 */
import { readFileSync, writeFileSync, existsSync, unlinkSync, renameSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

import {
  parseFrontmatter,
  serializeFrontmatter,
  type Frontmatter,
} from "./frontmatter.js";
import { appendEvent, makeEvent } from "./project-board.js";

export const TASK_STATUSES = ["todo", "doing", "done", "blocked"] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

const SLUG_RE = /^[a-z0-9][a-z0-9_-]{0,39}$/;

export interface CreateTaskInput {
  slug: string;
  title: string;
  status?: TaskStatus;
  phase?: "now" | "next" | "later";
  estimate?: number;
  dependsOn?: string[];
  cycle?: string;
  epic?: string;
  body?: string;
  /** Override actor for this write. Defaults to CRAWFISH_ACTOR or "local". */
  actor?: string;
}

function tasksDir(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "tasks");
}

function taskPath(repoRoot: string, slug: string): string {
  return join(tasksDir(repoRoot), `${slug}.md`);
}

function assertValidSlug(slug: string): void {
  if (!SLUG_RE.test(slug)) {
    throw new Error(`invalid_task_slug: ${slug}`);
  }
}

function withActor<T>(actor: string | undefined, fn: () => T): T {
  if (!actor) return fn();
  const prev = process.env.CRAWFISH_ACTOR;
  process.env.CRAWFISH_ACTOR = actor;
  try {
    return fn();
  } finally {
    if (prev === undefined) delete process.env.CRAWFISH_ACTOR;
    else process.env.CRAWFISH_ACTOR = prev;
  }
}

/**
 * Create a new task. Throws if the slug already exists.
 */
export function createTask(repoRoot: string, input: CreateTaskInput): string {
  assertValidSlug(input.slug);
  const path = taskPath(repoRoot, input.slug);
  if (existsSync(path)) {
    throw new Error(`task_already_exists: ${input.slug}`);
  }
  mkdirSync(dirname(path), { recursive: true });

  const fm: Frontmatter = {
    id: input.slug,
    title: input.title,
    status: input.status ?? "todo",
  };
  if (input.phase) fm.phase = input.phase;
  if (typeof input.estimate === "number") fm.estimate = input.estimate;
  if (input.dependsOn) fm["depends-on"] = input.dependsOn;
  if (input.cycle) fm.cycle = input.cycle;
  if (input.epic) fm.epic = input.epic;

  const body = input.body ?? `# ${input.title}\n`;
  writeFileSync(path, serializeFrontmatter(fm, body), "utf8");

  withActor(input.actor, () => {
    appendEvent(
      repoRoot,
      makeEvent("task_created", {
        task_id: input.slug,
        payload: {
          title: input.title,
          status: fm.status,
          phase: fm.phase,
          estimate: fm.estimate,
          cycle: input.cycle,
          epic: input.epic,
        },
      }),
    );
  });

  return path;
}

export interface UpdateTaskPatch {
  title?: string;
  status?: TaskStatus;
  phase?: "now" | "next" | "later";
  estimate?: number;
  dependsOn?: string[];
  cycle?: string | null;
  epic?: string | null;
  body?: string;
  actor?: string;
}

/**
 * Apply a partial update to a task. Emits `task_updated` plus any
 * specialized event (`task_status_changed`, `task_added_to_cycle`, …) the
 * patch warrants. Idempotent: a patch that changes nothing emits no events.
 */
export function updateTask(
  repoRoot: string,
  slug: string,
  patch: UpdateTaskPatch,
): void {
  assertValidSlug(slug);
  const path = taskPath(repoRoot, slug);
  if (!existsSync(path)) {
    throw new Error(`task_not_found: ${slug}`);
  }
  const raw = readFileSync(path, "utf8");
  const { fm, body } = parseFrontmatter(raw);

  const before = { ...fm };
  let changed = false;

  if (patch.title !== undefined && fm.title !== patch.title) {
    fm.title = patch.title;
    changed = true;
  }
  if (patch.status !== undefined && fm.status !== patch.status) {
    fm.status = patch.status;
    changed = true;
  }
  if (patch.phase !== undefined && fm.phase !== patch.phase) {
    fm.phase = patch.phase;
    changed = true;
  }
  if (patch.estimate !== undefined && fm.estimate !== patch.estimate) {
    fm.estimate = patch.estimate;
    changed = true;
  }
  if (patch.dependsOn !== undefined) {
    fm["depends-on"] = patch.dependsOn;
    changed = true;
  }
  if (patch.cycle !== undefined) {
    if (patch.cycle === null) {
      if (fm.cycle !== undefined) {
        delete fm.cycle;
        changed = true;
      }
    } else if (fm.cycle !== patch.cycle) {
      fm.cycle = patch.cycle;
      changed = true;
    }
  }
  if (patch.epic !== undefined) {
    if (patch.epic === null) {
      if (fm.epic !== undefined) {
        delete fm.epic;
        changed = true;
      }
    } else if (fm.epic !== patch.epic) {
      fm.epic = patch.epic;
      changed = true;
    }
  }

  const finalBody = patch.body !== undefined ? patch.body : body;
  if (patch.body !== undefined && patch.body !== body) {
    changed = true;
  }

  if (!changed) return;

  writeFileSync(path, serializeFrontmatter(fm, finalBody), "utf8");

  withActor(patch.actor, () => {
    appendEvent(
      repoRoot,
      makeEvent("task_updated", {
        task_id: slug,
        payload: { before, after: { ...fm } },
      }),
    );
    if (patch.status !== undefined && before.status !== patch.status) {
      appendEvent(
        repoRoot,
        makeEvent("task_status_changed", {
          task_id: slug,
          payload: { from: before.status, to: patch.status },
        }),
      );
    }
    if (patch.cycle !== undefined) {
      const fromCycle = (before.cycle as string | undefined) ?? null;
      const toCycle = patch.cycle;
      if (fromCycle && fromCycle !== toCycle) {
        appendEvent(
          repoRoot,
          makeEvent("task_removed_from_cycle", {
            task_id: slug,
            cycle_id: fromCycle,
          }),
        );
      }
      if (toCycle && toCycle !== fromCycle) {
        appendEvent(
          repoRoot,
          makeEvent("task_added_to_cycle", {
            task_id: slug,
            cycle_id: toCycle,
          }),
        );
      }
    }
    if (patch.epic !== undefined) {
      const fromEpic = (before.epic as string | undefined) ?? null;
      const toEpic = patch.epic;
      if (fromEpic && fromEpic !== toEpic) {
        appendEvent(
          repoRoot,
          makeEvent("task_removed_from_epic", {
            task_id: slug,
            epic_id: fromEpic,
          }),
        );
      }
      if (toEpic && toEpic !== fromEpic) {
        appendEvent(
          repoRoot,
          makeEvent("task_added_to_epic", {
            task_id: slug,
            epic_id: toEpic,
          }),
        );
      }
    }
  });
}

export function renameTask(
  repoRoot: string,
  oldSlug: string,
  newSlug: string,
  actor?: string,
): void {
  assertValidSlug(oldSlug);
  assertValidSlug(newSlug);
  if (oldSlug === newSlug) return;
  const oldPath = taskPath(repoRoot, oldSlug);
  const newPath = taskPath(repoRoot, newSlug);
  if (!existsSync(oldPath)) throw new Error(`task_not_found: ${oldSlug}`);
  if (existsSync(newPath)) throw new Error(`task_already_exists: ${newSlug}`);
  renameSync(oldPath, newPath);
  const raw = readFileSync(newPath, "utf8");
  const { fm, body } = parseFrontmatter(raw);
  fm.id = newSlug;
  writeFileSync(newPath, serializeFrontmatter(fm, body), "utf8");
  withActor(actor, () => {
    appendEvent(
      repoRoot,
      makeEvent("task_renamed", {
        task_id: newSlug,
        payload: { from: oldSlug, to: newSlug },
      }),
    );
  });
}

export function deleteTask(repoRoot: string, slug: string, actor?: string): void {
  assertValidSlug(slug);
  const path = taskPath(repoRoot, slug);
  if (!existsSync(path)) return;
  unlinkSync(path);
  withActor(actor, () => {
    appendEvent(repoRoot, makeEvent("task_deleted", { task_id: slug }));
  });
}

export interface TaskRecord {
  slug: string;
  frontmatter: Frontmatter;
  body: string;
}

export function readTask(repoRoot: string, slug: string): TaskRecord | null {
  assertValidSlug(slug);
  const path = taskPath(repoRoot, slug);
  if (!existsSync(path)) return null;
  const { fm, body } = parseFrontmatter(readFileSync(path, "utf8"));
  return { slug, frontmatter: fm, body };
}
