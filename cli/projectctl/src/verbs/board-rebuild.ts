/**
 * `craw board rebuild` — disaster-recovery + upgrade path for ADR-001.
 *
 * Walks `.crawfish/tasks/*.md` and `.crawfish/cycles/*.json` and rewrites
 * `.crawfish/board.jsonl` from scratch as a sequence of synthetic events
 * that describe the *current* state. Useful when:
 *
 *   - A project pre-dates the journal and has `.md` files but no jsonl.
 *   - The journal got corrupted or out of sync with the files.
 *   - The `/crawfish-roadmap` skill wrote files directly without emitting
 *     events.
 *
 * Always a full rebuild for Stage 1 — incremental rebuild is deferred.
 */
import { readFileSync, writeFileSync, existsSync, readdirSync, mkdirSync, statSync, renameSync } from "node:fs";
import { dirname, join } from "node:path";

import { boardPath, type ProjectBoardEvent, type ProjectBoardEventType } from "../project-board.js";
import { parseFrontmatter } from "../frontmatter.js";

export interface RebuildResult {
  events_written: number;
  tasks_seen: number;
  cycles_seen: number;
  epics_seen: number;
}

interface TaskFile {
  slug: string;
  mtime: number;
  fm: Record<string, unknown>;
}

export function boardRebuild(repoRoot: string): RebuildResult {
  const tasksDir = join(repoRoot, ".crawfish", "tasks");
  const cyclesDir = join(repoRoot, ".crawfish", "cycles");
  const epicsDir = join(repoRoot, ".crawfish", "epics");

  const events: ProjectBoardEvent[] = [];
  const actor = process.env.CRAWFISH_ACTOR ?? "rebuild";

  // Cycles first — tasks may reference them.
  let cyclesSeen = 0;
  if (existsSync(cyclesDir)) {
    const entries = readdirSync(cyclesDir)
      .filter((n) => n.endsWith(".json"))
      .map((n) => ({ name: n, mtime: statSync(join(cyclesDir, n)).mtimeMs }))
      .sort((a, b) => a.mtime - b.mtime);
    for (const { name } of entries) {
      try {
        const cycle = JSON.parse(readFileSync(join(cyclesDir, name), "utf8"));
        cyclesSeen++;
        events.push(synth("cycle_created", new Date(cycle.created_at ?? Date.now()).toISOString(), actor, {
          cycle_id: cycle.id,
          payload: {
            name: cycle.name,
            start: cycle.start,
            end: cycle.end,
            token_budget: cycle.token_budget,
          },
        }));
        if (cycle.status === "closed") {
          events.push(synth("cycle_closed", new Date().toISOString(), actor, { cycle_id: cycle.id }));
        }
      } catch {
        /* skip unreadable */
      }
    }
  }

  // Epics second.
  let epicsSeen = 0;
  if (existsSync(epicsDir)) {
    const entries = readdirSync(epicsDir)
      .filter((n) => n.endsWith(".md"))
      .map((n) => ({ name: n, mtime: statSync(join(epicsDir, n)).mtimeMs }))
      .sort((a, b) => a.mtime - b.mtime);
    for (const { name } of entries) {
      try {
        const raw = readFileSync(join(epicsDir, name), "utf8");
        const { fm } = parseFrontmatter(raw);
        const id = typeof fm.id === "string" ? fm.id : name.replace(/\.md$/, "");
        epicsSeen++;
        events.push(synth("epic_created", new Date().toISOString(), actor, {
          epic_id: id,
          payload: { title: fm.title, parent_cycle: fm["parent-cycle"] ?? fm.parent_cycle },
        }));
      } catch {
        /* skip */
      }
    }
  }

  // Tasks last — emit task_created in mtime order, then attachment events.
  const tasks: TaskFile[] = [];
  if (existsSync(tasksDir)) {
    for (const name of readdirSync(tasksDir)) {
      if (!name.endsWith(".md")) continue;
      const slug = name.slice(0, -3);
      if (!/^[a-z0-9][a-z0-9_-]{0,39}$/.test(slug)) continue;
      try {
        const path = join(tasksDir, name);
        const { fm } = parseFrontmatter(readFileSync(path, "utf8"));
        tasks.push({ slug, mtime: statSync(path).mtimeMs, fm: fm as Record<string, unknown> });
      } catch {
        /* skip */
      }
    }
  }
  tasks.sort((a, b) => a.mtime - b.mtime);

  for (const t of tasks) {
    const ts = new Date(t.mtime).toISOString();
    events.push(synth("task_created", ts, actor, {
      task_id: t.slug,
      payload: {
        title: t.fm.title,
        status: t.fm.status ?? "todo",
        phase: t.fm.phase,
        estimate: t.fm.estimate,
        cycle: t.fm.cycle,
        epic: t.fm.epic,
      },
    }));
    if (typeof t.fm.cycle === "string" && t.fm.cycle.length > 0) {
      events.push(synth("task_added_to_cycle", ts, actor, {
        task_id: t.slug,
        cycle_id: t.fm.cycle,
      }));
    }
    if (typeof t.fm.epic === "string" && t.fm.epic.length > 0) {
      events.push(synth("task_added_to_epic", ts, actor, {
        task_id: t.slug,
        epic_id: t.fm.epic,
      }));
    }
  }

  // Write atomically: temp file → rename.
  const path = boardPath(repoRoot);
  mkdirSync(dirname(path), { recursive: true });
  const tmp = path + ".tmp";
  const body = events.map((e) => JSON.stringify(e)).join("\n") + (events.length > 0 ? "\n" : "");
  writeFileSync(tmp, body, "utf8");
  renameSync(tmp, path);

  return {
    events_written: events.length,
    tasks_seen: tasks.length,
    cycles_seen: cyclesSeen,
    epics_seen: epicsSeen,
  };
}

function synth(
  type: ProjectBoardEventType,
  ts: string,
  actor: string,
  fields: Omit<ProjectBoardEvent, "ts" | "actor" | "type">,
): ProjectBoardEvent {
  return { ts, actor, type, ...fields };
}
