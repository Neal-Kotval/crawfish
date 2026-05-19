#!/usr/bin/env node
/**
 * crawfish-orgctl MCP server entrypoint.
 *
 * Tools (spec §6):
 *   board_list_tasks    — folded task list, optional status/assignee filter
 *   board_create_task   — append task_created event, returns ULID
 *   board_update_task   — append task_updated event (idempotent on retry)
 *   board_comment       — append task_commented event
 *   org_fs_list         — list <org>/files/ recursively
 *   org_fs_read         — read one file under <org>/files/ (≤1 MiB)
 *   org_fs_write        — write one file under <org>/files/ (≤1 MiB, idempotent)
 *
 * Every response carries `tokens_used` per the crawfish optimizer
 * contract (v1.0). Errors: `{ tokens_used: 0, error: { code, message } }`.
 */
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { OrgError } from "./orgs.js";
import {
  listTasks,
  createTask,
  updateTask,
  commentTask,
} from "./board.js";
import { listFiles, readFile, writeFile } from "./files.js";
import { tokensOf } from "./tokens.js";
import { ACTIVITY_TOOL_DEFS, dispatchActivity } from "./tools/activity.js";
import { PREFLIGHT_TOOL_DEFS, dispatchPreflight, type PreflightArgs } from "./preflight.js";
import { CRITERIA_TOOL_DEFS, dispatchCriteria } from "./criteria.js";
import { BUDGET_TOOL_DEFS, dispatchBudget } from "./budget.js";

const server = new Server(
  { name: "crawfish-orgctl", version: "0.1.0" },
  { capabilities: { tools: {} } },
);

const TOOL_DEFS = [
  {
    name: "board_list_tasks",
    description:
      "List folded tasks for an org, optionally filtered by status or assignee. Reads the append-only board.jsonl and replays events into Task records.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string", description: "ULID of the org." },
        status: {
          type: "string",
          enum: ["backlog", "in_progress", "review", "done"],
        },
        assignee: { type: "string", description: "Member id." },
      },
      required: ["org_id"],
    },
  },
  {
    name: "board_create_task",
    description:
      "Append a task_created event. Returns the new task_id (ULID). Default status is 'backlog'.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string" },
        title: { type: "string" },
        description: { type: "string" },
        assignee: { type: ["string", "null"], description: "Member id or null." },
        by: { type: "string", description: "Creating member's id." },
      },
      required: ["org_id", "title", "description", "by"],
    },
  },
  {
    name: "board_update_task",
    description:
      "Append a task_updated event. `patch` may include title/description/assignee/status. Idempotent: re-applying the same patch is safe.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string" },
        task_id: { type: "string" },
        by: { type: "string" },
        patch: {
          type: "object",
          properties: {
            title: { type: "string" },
            description: { type: "string" },
            assignee: { type: "string" },
            status: {
              type: "string",
              enum: ["backlog", "in_progress", "review", "done"],
            },
          },
        },
      },
      required: ["org_id", "task_id", "by", "patch"],
    },
  },
  {
    name: "board_comment",
    description: "Append a task_commented event.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string" },
        task_id: { type: "string" },
        by: { type: "string" },
        body: { type: "string" },
      },
      required: ["org_id", "task_id", "by", "body"],
    },
  },
  {
    name: "org_fs_list",
    description:
      "List entries under the org's hosted files/ directory. Returns { path, kind, size, mtime } sorted by path.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string" },
        prefix: { type: "string", description: "Relative directory prefix filter." },
      },
      required: ["org_id"],
    },
  },
  {
    name: "org_fs_read",
    description:
      "Read a single file under <org>/files/. Path-safe; rejects '..', absolute paths, null bytes. 1 MiB max → too_large.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string" },
        path: { type: "string" },
      },
      required: ["org_id", "path"],
    },
  },
  {
    name: "org_fs_write",
    description:
      "Write content to a file under <org>/files/. Creates parent dirs. Idempotent: writing the same content twice is a no-op. 1 MiB max → too_large.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string" },
        path: { type: "string" },
        content: { type: "string" },
      },
      required: ["org_id", "path", "content"],
    },
  },
  // Phase 3 — activity / comments / mentions
  ...ACTIVITY_TOOL_DEFS,
  // NOW-W2 — preflight / acceptance criteria / budget breach
  ...PREFLIGHT_TOOL_DEFS,
  ...CRITERIA_TOOL_DEFS,
  ...BUDGET_TOOL_DEFS,
];

/** Shape of one tool response (with tokens_used computed last). */
type ToolPayload = Record<string, unknown>;

async function dispatch(name: string, args: Record<string, unknown>): Promise<ToolPayload> {
  switch (name) {
    case "board_list_tasks": {
      const tasks = await listTasks(args.org_id as string, {
        status: args.status as string | undefined,
        assignee: args.assignee as string | undefined,
      });
      return { tasks };
    }
    case "board_create_task": {
      const task_id = await createTask(args.org_id as string, {
        title: args.title as string,
        description: args.description as string,
        assignee: (args.assignee as string | null | undefined) ?? null,
        by: args.by as string,
      });
      return { task_id };
    }
    case "board_update_task": {
      await updateTask(args.org_id as string, {
        task_id: args.task_id as string,
        by: args.by as string,
        patch: (args.patch ?? {}) as any,
      });
      return { ok: true };
    }
    case "board_comment": {
      await commentTask(args.org_id as string, {
        task_id: args.task_id as string,
        by: args.by as string,
        body: args.body as string,
      });
      return { ok: true };
    }
    case "org_fs_list": {
      const entries = await listFiles(args.org_id as string, args.prefix as string | undefined);
      return { entries };
    }
    case "org_fs_read": {
      const r = await readFile(args.org_id as string, args.path as string);
      return r;
    }
    case "org_fs_write": {
      const r = await writeFile(args.org_id as string, args.path as string, args.content as string);
      return r;
    }
    default:
      if (name.startsWith("activity_")) {
        return dispatchActivity(name, args);
      }
      if (name === "preflight_attest") {
        return dispatchPreflight(args as unknown as PreflightArgs);
      }
      if (name.startsWith("criteria_")) {
        return dispatchCriteria(name, args);
      }
      if (name === "task_budget_report" || name.startsWith("budget_")) {
        return dispatchBudget(name, args);
      }
      throw new OrgError("not_found", `unknown tool: ${name}`);
  }
}

/** Run a tool and stamp `tokens_used` / error envelope per contract §6. */
export async function runTool(
  name: string,
  args: Record<string, unknown>,
): Promise<ToolPayload> {
  try {
    const payload = await dispatch(name, args);
    const withTokens = { ...payload, tokens_used: 0 };
    withTokens.tokens_used = tokensOf(withTokens);
    return withTokens;
  } catch (err) {
    if (err instanceof OrgError) {
      return { tokens_used: 0, error: { code: err.code, message: err.message } };
    }
    return {
      tokens_used: 0,
      error: { code: "internal", message: err instanceof Error ? err.message : String(err) },
    };
  }
}

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOL_DEFS }));

server.setRequestHandler(CallToolRequestSchema, async (req) => {
  const { name, arguments: args } = req.params;
  const result = await runTool(name, (args ?? {}) as Record<string, unknown>);
  const isError = "error" in result;
  process.stderr.write(
    `[crawfish-orgctl] ${name} → ${result.tokens_used} tokens${isError ? " (error)" : ""}\n`,
  );
  return {
    content: [{ type: "text", text: JSON.stringify(result) }],
    ...(isError ? { isError: true } : {}),
  };
});

// Only start the stdio transport when run as a script, not when imported by tests.
const isMain = import.meta.url === `file://${process.argv[1]}`;
if (isMain) {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write("crawfish-orgctl MCP server ready (stdio)\n");
}
