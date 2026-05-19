/**
 * Project-level epics — Week 1.1 of the NOW phase, sibling to cycles.
 *
 * An epic groups related tasks under a single deliverable. Unlike cycles,
 * epics are open-ended (no time box). They optionally roll up under a
 * cycle for time-boxed planning.
 *
 * Epics live as `.md` files at `<repoRoot>/.crawfish/epics/<id>.md` with
 * YAML frontmatter (id, title, parent-cycle, status). The body is free-form
 * markdown — typically the epic's acceptance criteria and decision log.
 *
 * Tasks reference an epic via `epic: epc_xxx` in their own frontmatter.
 * `computeEpicRollup` sums estimates over tasks that point at this epic.
 */
import {
  readFileSync,
  writeFileSync,
  existsSync,
  readdirSync,
  mkdirSync,
} from "node:fs";
import { join } from "node:path";

import {
  parseFrontmatter,
  serializeFrontmatter,
  type Frontmatter,
} from "./frontmatter.js";
import { appendEvent, makeEvent } from "./project-board.js";

const ID_RE = /^epc_[A-Z0-9]{1,32}$/;

export interface Epic {
  id: string;
  title: string;
  parent_cycle: string | null;
  status: "open" | "closed";
  body: string;
}

export interface EpicRollup {
  epic: Epic;
  task_count: number;
  estimate_used: number;
  by_status: { todo: number; doing: number; done: number; blocked: number };
}

function epicsDir(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "epics");
}

function epicPath(repoRoot: string, id: string): string {
  return join(epicsDir(repoRoot), `${id}.md`);
}

function tasksDir(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "tasks");
}

function assertValidId(id: string): void {
  if (!ID_RE.test(id)) throw new Error(`invalid_epic_id: ${id}`);
}

export interface CreateEpicInput {
  id: string;
  title: string;
  parent_cycle?: string | null;
  body?: string;
  actor?: string;
}

export function createEpic(repoRoot: string, input: CreateEpicInput): string {
  assertValidId(input.id);
  const path = epicPath(repoRoot, input.id);
  if (existsSync(path)) throw new Error(`epic_already_exists: ${input.id}`);
  mkdirSync(epicsDir(repoRoot), { recursive: true });

  const fm: Frontmatter = {
    id: input.id,
    title: input.title,
    status: "open",
  };
  if (input.parent_cycle) fm["parent-cycle"] = input.parent_cycle;

  const body = input.body ?? `# ${input.title}\n`;
  writeFileSync(path, serializeFrontmatter(fm, body), "utf8");

  const prevActor = process.env.CRAWFISH_ACTOR;
  if (input.actor) process.env.CRAWFISH_ACTOR = input.actor;
  try {
    appendEvent(
      repoRoot,
      makeEvent("epic_created", {
        epic_id: input.id,
        payload: {
          title: input.title,
          parent_cycle: input.parent_cycle ?? null,
        },
      }),
    );
  } finally {
    if (input.actor) {
      if (prevActor === undefined) delete process.env.CRAWFISH_ACTOR;
      else process.env.CRAWFISH_ACTOR = prevActor;
    }
  }

  return path;
}

export function readEpic(repoRoot: string, id: string): Epic | null {
  assertValidId(id);
  const path = epicPath(repoRoot, id);
  if (!existsSync(path)) return null;
  const { fm, body } = parseFrontmatter(readFileSync(path, "utf8"));
  return {
    id: typeof fm.id === "string" ? fm.id : id,
    title: typeof fm.title === "string" ? fm.title : "",
    parent_cycle: typeof fm["parent-cycle"] === "string" ? fm["parent-cycle"] : null,
    status: fm.status === "closed" ? "closed" : "open",
    body,
  };
}

export function listEpics(repoRoot: string): Epic[] {
  const dir = epicsDir(repoRoot);
  if (!existsSync(dir)) return [];
  const epics: Epic[] = [];
  for (const name of readdirSync(dir)) {
    if (!name.endsWith(".md")) continue;
    const id = name.slice(0, -3);
    if (!ID_RE.test(id)) continue;
    const e = readEpic(repoRoot, id);
    if (e) epics.push(e);
  }
  return epics.sort((a, b) => a.id.localeCompare(b.id));
}

export interface UpdateEpicPatch {
  title?: string;
  parent_cycle?: string | null;
  status?: "open" | "closed";
  body?: string;
  actor?: string;
}

export function updateEpic(
  repoRoot: string,
  id: string,
  patch: UpdateEpicPatch,
): void {
  assertValidId(id);
  const path = epicPath(repoRoot, id);
  if (!existsSync(path)) throw new Error(`epic_not_found: ${id}`);
  const { fm, body } = parseFrontmatter(readFileSync(path, "utf8"));
  const before = { ...fm };
  let changed = false;

  if (patch.title !== undefined && fm.title !== patch.title) {
    fm.title = patch.title;
    changed = true;
  }
  if (patch.parent_cycle !== undefined) {
    if (patch.parent_cycle === null) {
      if (fm["parent-cycle"] !== undefined) {
        delete fm["parent-cycle"];
        changed = true;
      }
    } else if (fm["parent-cycle"] !== patch.parent_cycle) {
      fm["parent-cycle"] = patch.parent_cycle;
      changed = true;
    }
  }
  if (patch.status !== undefined && fm.status !== patch.status) {
    fm.status = patch.status;
    changed = true;
  }
  const finalBody = patch.body !== undefined ? patch.body : body;
  if (patch.body !== undefined && patch.body !== body) changed = true;

  if (!changed) return;

  writeFileSync(path, serializeFrontmatter(fm, finalBody), "utf8");

  const prevActor = process.env.CRAWFISH_ACTOR;
  if (patch.actor) process.env.CRAWFISH_ACTOR = patch.actor;
  try {
    appendEvent(
      repoRoot,
      makeEvent("epic_updated", {
        epic_id: id,
        payload: { before, after: { ...fm } },
      }),
    );
    if (patch.status === "closed" && before.status !== "closed") {
      appendEvent(repoRoot, makeEvent("epic_closed", { epic_id: id }));
    }
  } finally {
    if (patch.actor) {
      if (prevActor === undefined) delete process.env.CRAWFISH_ACTOR;
      else process.env.CRAWFISH_ACTOR = prevActor;
    }
  }
}

/**
 * Walk `.crawfish/tasks/*.md` and aggregate tasks whose `epic` field
 * points at `id`. Mirrors the cycle rollup shape so the dash can render
 * both in the same view.
 */
export function computeEpicRollup(repoRoot: string, id: string): EpicRollup | null {
  const epic = readEpic(repoRoot, id);
  if (!epic) return null;
  const dir = tasksDir(repoRoot);
  const by_status = { todo: 0, doing: 0, done: 0, blocked: 0 };
  let task_count = 0;
  let estimate_used = 0;
  if (existsSync(dir)) {
    for (const name of readdirSync(dir)) {
      if (!name.endsWith(".md")) continue;
      try {
        const raw = readFileSync(join(dir, name), "utf8");
        const { fm } = parseFrontmatter(raw);
        if (fm.epic !== id) continue;
        task_count++;
        if (typeof fm.estimate === "number") estimate_used += fm.estimate;
        const status = (fm.status as string) ?? "todo";
        if (
          status === "todo" ||
          status === "doing" ||
          status === "done" ||
          status === "blocked"
        ) {
          by_status[status as keyof typeof by_status]++;
        }
      } catch {
        /* skip */
      }
    }
  }
  return { epic, task_count, estimate_used, by_status };
}
