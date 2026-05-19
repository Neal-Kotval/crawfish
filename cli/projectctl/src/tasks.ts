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
  type Criterion,
  type CriterionEvidence,
  type TaskLink,
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
  criteria?: Criterion[];
  links?: TaskLink[];
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
  if (input.criteria && input.criteria.length > 0) fm.criteria = input.criteria;
  if (input.links && input.links.length > 0) fm.links = input.links.map((l) => ({ ...l }));

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
  /** Assignee agent id (or null to clear). Emits `task_assigned`. */
  assignee?: string | null;
  /** Who/what assigned. Defaults to "human". The router passes "router". */
  assignedBy?: string;
  /** Replace the whole criteria array (matches `criteria_set` MCP semantics). */
  criteria?: Criterion[];
  /** Attest a single criterion: store its evidence. */
  setCriterionEvidence?: { id: string; evidence: CriterionEvidence };
  /** Clear evidence from a single criterion. */
  clearCriterionEvidence?: { id: string; by: string };
  /** Replace the full links array. Emits per-link task_linked / task_unlinked diff events. */
  links?: TaskLink[];
  body?: string;
  actor?: string;
}

function readCriteria(fm: Frontmatter): Criterion[] {
  const v = fm.criteria;
  if (Array.isArray(v) && v.length > 0 && typeof v[0] === "object" && v[0] !== null && "id" in (v[0] as object)) {
    return (v as Criterion[]).map((c) => ({ ...c, evidence: c.evidence ? { ...c.evidence } : undefined }));
  }
  return [];
}

function writeCriteria(fm: Frontmatter, criteria: Criterion[]): void {
  if (criteria.length === 0) delete fm.criteria;
  else fm.criteria = criteria;
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
  const beforeCriteria = readCriteria(fm);
  let changed = false;

  // Apply criteria mutations BEFORE the status/done-guard so that setting
  // evidence and transitioning to done in the same patch is allowed.
  let nextCriteria = beforeCriteria;
  let criteriaReplaced = false;
  let metCriterion: Criterion | null = null;
  let clearedId: string | null = null;
  let clearedBy: string | null = null;

  if (patch.criteria !== undefined) {
    nextCriteria = patch.criteria.map((c) => ({ ...c, evidence: c.evidence ? { ...c.evidence } : undefined }));
    criteriaReplaced = true;
    changed = true;
  }
  if (patch.setCriterionEvidence) {
    const { id, evidence } = patch.setCriterionEvidence;
    const idx = nextCriteria.findIndex((c) => c.id === id);
    if (idx < 0) throw new Error(`unknown_criterion: ${id}`);
    nextCriteria = nextCriteria.map((c, i) => (i === idx ? { ...c, evidence: { ...evidence } } : c));
    metCriterion = nextCriteria[idx];
    changed = true;
  }
  if (patch.clearCriterionEvidence) {
    const { id, by } = patch.clearCriterionEvidence;
    const idx = nextCriteria.findIndex((c) => c.id === id);
    if (idx < 0) throw new Error(`unknown_criterion: ${id}`);
    nextCriteria = nextCriteria.map((c, i) => {
      if (i !== idx) return c;
      const { evidence: _e, ...rest } = c;
      return rest;
    });
    clearedId = id;
    clearedBy = by;
    changed = true;
  }

  if (patch.title !== undefined && fm.title !== patch.title) {
    fm.title = patch.title;
    changed = true;
  }
  if (patch.status !== undefined && fm.status !== patch.status) {
    if (patch.status === "done") {
      const unmet = nextCriteria.filter((c) => !c.evidence).map((c) => c.id);
      if (unmet.length > 0) {
        throw new Error(
          `criteria_unmet: ${JSON.stringify({ code: "criteria_unmet", task_id: slug, unmet })}`,
        );
      }
    }
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
  let assigneeChanged = false;
  let assigneeFrom: string | null = null;
  let assigneeTo: string | null = null;
  if (patch.assignee !== undefined) {
    const fromVal = typeof fm.assignee === "string" ? fm.assignee : undefined;
    if (patch.assignee === null) {
      if (fromVal !== undefined) {
        delete fm.assignee;
        assigneeChanged = true;
        assigneeFrom = fromVal;
        assigneeTo = null;
        changed = true;
      }
    } else if (fromVal !== patch.assignee) {
      assigneeFrom = fromVal ?? null;
      assigneeTo = patch.assignee;
      fm.assignee = patch.assignee;
      assigneeChanged = true;
      changed = true;
    }
  }

  const beforeLinks = readLinks(fm);
  let nextLinks = beforeLinks;
  let linksReplaced = false;
  if (patch.links !== undefined) {
    nextLinks = patch.links.map((l) => ({ ...l }));
    if (!linksEqual(beforeLinks, nextLinks)) {
      linksReplaced = true;
      changed = true;
    }
  }

  const finalBody = patch.body !== undefined ? patch.body : body;
  if (patch.body !== undefined && patch.body !== body) {
    changed = true;
  }

  if (!changed) return;

  if (linksReplaced) writeLinks(fm, nextLinks);
  writeCriteria(fm, nextCriteria);
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
    if (assigneeChanged) {
      appendEvent(
        repoRoot,
        makeEvent("task_assigned", {
          task_id: slug,
          payload: {
            from: assigneeFrom,
            to: assigneeTo,
            by: patch.assignedBy ?? "human",
          },
        }),
      );
    }
    if (criteriaReplaced) {
      appendEvent(
        repoRoot,
        makeEvent("criterion_set", {
          task_id: slug,
          payload: { criteria: nextCriteria },
        }),
      );
    }
    if (metCriterion && metCriterion.evidence) {
      appendEvent(
        repoRoot,
        makeEvent("criterion_met", {
          task_id: slug,
          payload: {
            id: metCriterion.id,
            kind: metCriterion.kind,
            evidence: metCriterion.evidence,
          },
        }),
      );
    }
    if (clearedId) {
      appendEvent(
        repoRoot,
        makeEvent("criterion_cleared", {
          task_id: slug,
          payload: { id: clearedId, by: clearedBy },
        }),
      );
    }
    if (linksReplaced) {
      const added = nextLinks.filter(
        (n) => !beforeLinks.some((b) => b.kind === n.kind && b.target_task_id === n.target_task_id),
      );
      const removed = beforeLinks.filter(
        (b) => !nextLinks.some((n) => n.kind === b.kind && n.target_task_id === b.target_task_id),
      );
      for (const l of added) {
        appendEvent(
          repoRoot,
          makeEvent("task_linked", {
            task_id: slug,
            payload: { kind: l.kind, target_task_id: l.target_task_id },
          }),
        );
      }
      for (const l of removed) {
        appendEvent(
          repoRoot,
          makeEvent("task_unlinked", {
            task_id: slug,
            payload: { kind: l.kind, target_task_id: l.target_task_id },
          }),
        );
      }
    }
  });
}

function readLinks(fm: Frontmatter): TaskLink[] {
  const v = fm.links;
  if (Array.isArray(v) && (v.length === 0 || (typeof v[0] === "object" && v[0] !== null && "kind" in (v[0] as object)))) {
    return (v as TaskLink[]).map((l) => ({ ...l }));
  }
  return [];
}

function writeLinks(fm: Frontmatter, links: TaskLink[]): void {
  if (links.length === 0) delete fm.links;
  else fm.links = links;
}

function linksEqual(a: TaskLink[], b: TaskLink[]): boolean {
  if (a.length !== b.length) return false;
  const key = (l: TaskLink) => `${l.kind}|${l.target_task_id}`;
  const sa = new Set(a.map(key));
  for (const l of b) if (!sa.has(key(l))) return false;
  return true;
}

export function readTaskLinks(repoRoot: string, slug: string): TaskLink[] {
  const t = readTask(repoRoot, slug);
  if (!t) return [];
  return readLinks(t.frontmatter);
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
