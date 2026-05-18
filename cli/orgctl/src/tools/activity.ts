/**
 * MCP tool group: activity_* tools.
 *
 * Exported as ACTIVITY_TOOL_DEFS + dispatchActivity so the lead can wire
 * them into crawfish-orgctl/src/index.ts at finalization without touching
 * this file.
 *
 * All responses conform to optimizer contract v1.0: `tokens_used` on every
 * response, error envelope `{ tokens_used: 0, error: { code, message } }`.
 */
import { OrgError } from "../orgs.js";
import {
  commentTask,
  updateTask,
  foldTasks,
  readEvents,
  type ActivityEntry,
} from "../board.js";
import { tokensOf } from "../tokens.js";

type ToolPayload = Record<string, unknown>;

// ---------- Tool definitions (schema for MCP ListTools) ----------

export const ACTIVITY_TOOL_DEFS = [
  {
    name: "activity_post_comment",
    description:
      "Post a comment on a task. Appends a task_commented event to board.jsonl and auto-watches the commenter. Returns { tokens_used, ok }.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string", description: "ULID of the org." },
        task_id: { type: "string", description: "ULID of the task." },
        by: { type: "string", description: "Member id posting the comment." },
        body: { type: "string", description: "Comment text. Use @member-id to mention." },
      },
      required: ["org_id", "task_id", "by", "body"],
    },
  },
  {
    name: "activity_list_for_task",
    description:
      "Return the full activity log for a task, including synthesized `mentioned` entries derived from @member patterns in comments. Returns { tokens_used, activity_log }.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string" },
        task_id: { type: "string" },
      },
      required: ["org_id", "task_id"],
    },
  },
  {
    name: "activity_mention",
    description:
      "Post a comment that explicitly mentions one or more members by id. Appends a task_commented event and auto-watches all mentioned members. Returns { tokens_used, ok }.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string" },
        task_id: { type: "string" },
        by: { type: "string", description: "Member id posting the mention." },
        mentions: {
          type: "array",
          items: { type: "string" },
          description: "Array of member ids to mention.",
        },
        body: { type: "string", description: "Comment body (should include @member-id tokens)." },
      },
      required: ["org_id", "task_id", "by", "mentions", "body"],
    },
  },
] as const;

// ---------- Dispatch ----------

async function activityPostComment(args: Record<string, unknown>): Promise<ToolPayload> {
  const { org_id, task_id, by, body } = args as {
    org_id: string;
    task_id: string;
    by: string;
    body: string;
  };
  await commentTask(org_id, { task_id, by, body });

  // Auto-watch: add commenter to watchers if not already present.
  const events = await readEvents(org_id);
  const tasks = foldTasks(events);
  const task = tasks.find((t) => t.id === task_id);
  if (task && !task.watchers.includes(by)) {
    await updateTask(org_id, {
      task_id,
      by,
      patch: { watchers: [...task.watchers, by] },
    });
  }

  return { ok: true };
}

async function activityListForTask(args: Record<string, unknown>): Promise<ToolPayload> {
  const { org_id, task_id } = args as { org_id: string; task_id: string };
  const events = await readEvents(org_id);
  const tasks = foldTasks(events);
  const task = tasks.find((t) => t.id === task_id);
  if (!task) {
    throw new OrgError("not_found", `task ${task_id} not found`);
  }

  // Synthesize `mentioned` entries from comment bodies (same logic as lens).
  const MENTION_RE = /@([\w-]+)/g;
  const enriched: ActivityEntry[] = [...task.activity_log];

  for (const ev of events) {
    if (ev.type !== "task_commented" || ev.task_id !== task_id) continue;
    const mentions: string[] = [];
    let m: RegExpExecArray | null;
    MENTION_RE.lastIndex = 0;
    while ((m = MENTION_RE.exec(ev.body)) !== null) mentions.push(m[1]);
    if (mentions.length > 0) {
      enriched.push({
        by: ev.by,
        at: ev.ts,
        kind: "mentioned",
        payload: { mentions, body: ev.body },
      });
    }
  }

  enriched.sort((a, b) => a.at.localeCompare(b.at));
  return { activity_log: enriched };
}

async function activityMention(args: Record<string, unknown>): Promise<ToolPayload> {
  const { org_id, task_id, by, mentions, body } = args as {
    org_id: string;
    task_id: string;
    by: string;
    mentions: string[];
    body: string;
  };

  await commentTask(org_id, { task_id, by, body });

  // Auto-watch commenter + all mentioned members.
  const events = await readEvents(org_id);
  const tasks = foldTasks(events);
  const task = tasks.find((t) => t.id === task_id);
  if (!task) throw new OrgError("not_found", `task ${task_id} not found`);

  const toAdd = [...new Set([by, ...mentions])].filter(
    (m) => !task.watchers.includes(m),
  );
  if (toAdd.length > 0) {
    await updateTask(org_id, {
      task_id,
      by,
      patch: { watchers: [...task.watchers, ...toAdd] },
    });
  }

  return { ok: true };
}

// ---------- Public dispatcher ----------

export async function dispatchActivity(
  name: string,
  args: Record<string, unknown>,
): Promise<ToolPayload> {
  try {
    let payload: ToolPayload;
    switch (name) {
      case "activity_post_comment":
        payload = await activityPostComment(args);
        break;
      case "activity_list_for_task":
        payload = await activityListForTask(args);
        break;
      case "activity_mention":
        payload = await activityMention(args);
        break;
      default:
        throw new OrgError("not_found", `unknown activity tool: ${name}`);
    }
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
