#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { init } from "../verbs/init.js";
import { refresh } from "../verbs/refresh.js";
import { status } from "../verbs/status.js";
import { decisionAdd } from "../verbs/decision-add.js";
import { memoryAppend } from "../verbs/memory-append.js";
import { boardRebuild } from "../verbs/board-rebuild.js";
import { createTask, updateTask, deleteTask, readTask, type TaskStatus } from "../tasks.js";
import { createCycle, listCycles, computeRollup } from "../cycles.js";
import { readEvents } from "../project-board.js";

const TOOLS = [
  { name: "project_init", description: "Scaffold .crawfish/ in the repo.", inputSchema: { type: "object", properties: { repo_root: { type: "string" } }, required: ["repo_root"] } },
  { name: "project_refresh", description: "Re-derive .crawfish/*.md from sources.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, files: { type: "array", items: { type: "string" } } }, required: ["repo_root"] } },
  { name: "project_status", description: "Report which .crawfish files are stale.", inputSchema: { type: "object", properties: { repo_root: { type: "string" } }, required: ["repo_root"] } },
  { name: "project_decision_add", description: "Append an ADR entry.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, title: { type: "string" }, body: { type: "string" } }, required: ["repo_root", "title", "body"] } },
  { name: "project_memory_append", description: "Append a deduped memory entry.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, text: { type: "string" } }, required: ["repo_root", "text"] } },
  { name: "project_read", description: "Read one .crawfish/*.md file.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, file: { type: "string" } }, required: ["repo_root", "file"] } },
  { name: "project_task_create", description: "Create a project task (.crawfish/tasks/<slug>.md) and append a task_created event.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, slug: { type: "string" }, title: { type: "string" }, status: { type: "string", enum: ["todo", "doing", "done", "blocked"] }, phase: { type: "string", enum: ["now", "next", "later"] }, estimate: { type: "number" }, cycle: { type: "string" }, epic: { type: "string" }, body: { type: "string" } }, required: ["repo_root", "slug", "title"] } },
  { name: "project_task_update", description: "Update fields on an existing task and append events.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, slug: { type: "string" }, title: { type: "string" }, status: { type: "string", enum: ["todo", "doing", "done", "blocked"] }, phase: { type: "string", enum: ["now", "next", "later"] }, estimate: { type: "number" }, cycle: { type: ["string", "null"] }, epic: { type: ["string", "null"] }, body: { type: "string" } }, required: ["repo_root", "slug"] } },
  { name: "project_task_delete", description: "Delete a task file and append task_deleted.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, slug: { type: "string" } }, required: ["repo_root", "slug"] } },
  { name: "project_task_get", description: "Read a single task with frontmatter + body.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, slug: { type: "string" } }, required: ["repo_root", "slug"] } },
  { name: "project_cycle_create", description: "Create a cycle (.crawfish/cycles/<id>.json) and emit cycle_created.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, id: { type: "string" }, name: { type: "string" }, start: { type: "string" }, end: { type: "string" }, token_budget: { type: "number" } }, required: ["repo_root", "id", "name", "start", "end", "token_budget"] } },
  { name: "project_cycle_list", description: "List all cycles in the project, sorted by start date.", inputSchema: { type: "object", properties: { repo_root: { type: "string" } }, required: ["repo_root"] } },
  { name: "project_cycle_rollup", description: "Compute token-budget rollup for a cycle (estimate used vs token_budget, status breakdown).", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, id: { type: "string" } }, required: ["repo_root", "id"] } },
  { name: "project_board_events", description: "Read the .crawfish/board.jsonl event log for the project.", inputSchema: { type: "object", properties: { repo_root: { type: "string" }, limit: { type: "number" } }, required: ["repo_root"] } },
  { name: "project_board_rebuild", description: "Rebuild .crawfish/board.jsonl from current task and cycle files. Disaster recovery.", inputSchema: { type: "object", properties: { repo_root: { type: "string" } }, required: ["repo_root"] } },
];

export async function dispatch(name: string, args: Record<string, unknown>): Promise<any> {
  const root = String(args.repo_root);
  switch (name) {
    case "project_init":
      return { result: await init(root) };
    case "project_refresh":
      return await refresh(root, { only: args.files as string[] | undefined });
    case "project_status":
      return await status(root);
    case "project_decision_add":
      decisionAdd(root, String(args.title), String(args.body));
      return { ok: true };
    case "project_memory_append":
      memoryAppend(root, String(args.text), []);
      return { ok: true };
    case "project_read": {
      const path = join(root, ".crawfish", String(args.file));
      if (!existsSync(path)) return { error: "file not found" };
      return { content: readFileSync(path, "utf8") };
    }
    case "project_task_create": {
      const path = createTask(root, {
        slug: String(args.slug),
        title: String(args.title),
        status: args.status as TaskStatus | undefined,
        phase: args.phase as "now" | "next" | "later" | undefined,
        estimate: typeof args.estimate === "number" ? args.estimate : undefined,
        cycle: typeof args.cycle === "string" ? args.cycle : undefined,
        epic: typeof args.epic === "string" ? args.epic : undefined,
        body: typeof args.body === "string" ? args.body : undefined,
      });
      return { ok: true, path };
    }
    case "project_task_update": {
      updateTask(root, String(args.slug), {
        title: typeof args.title === "string" ? args.title : undefined,
        status: args.status as TaskStatus | undefined,
        phase: args.phase as "now" | "next" | "later" | undefined,
        estimate: typeof args.estimate === "number" ? args.estimate : undefined,
        cycle: args.cycle === null ? null : (typeof args.cycle === "string" ? args.cycle : undefined),
        epic: args.epic === null ? null : (typeof args.epic === "string" ? args.epic : undefined),
        body: typeof args.body === "string" ? args.body : undefined,
      });
      return { ok: true };
    }
    case "project_task_delete":
      deleteTask(root, String(args.slug));
      return { ok: true };
    case "project_task_get": {
      const t = readTask(root, String(args.slug));
      if (!t) return { error: "task_not_found" };
      return t;
    }
    case "project_cycle_create": {
      const c = createCycle(root, {
        id: String(args.id),
        name: String(args.name),
        start: String(args.start),
        end: String(args.end),
        token_budget: Number(args.token_budget),
      });
      return c;
    }
    case "project_cycle_list":
      return { cycles: listCycles(root) };
    case "project_cycle_rollup": {
      const r = computeRollup(root, String(args.id));
      if (!r) return { error: "cycle_not_found" };
      return r;
    }
    case "project_board_events": {
      const events = readEvents(root);
      const limit = typeof args.limit === "number" ? args.limit : undefined;
      return { events: limit ? events.slice(-limit) : events };
    }
    case "project_board_rebuild":
      return boardRebuild(root);
    default:
      throw new Error(`unknown tool: ${name}`);
  }
}

async function main(): Promise<void> {
  const server = new Server({ name: "crawfish-projectctl", version: "0.1.0" }, { capabilities: { tools: {} } });
  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));
  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const result = await dispatch(req.params.name, req.params.arguments ?? {});
    return { content: [{ type: "text", text: JSON.stringify(result) }] };
  });
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((e) => { console.error(e); process.exit(1); });
}
