/**
 * board.jsonl helpers per spec §3. Append-only event log; folded state is
 * derived on read. Never rewrite the file — every mutation is an `appendFile`.
 */
import * as fs from "node:fs";
import * as fsp from "node:fs/promises";
import * as path from "node:path";
import { OrgError, requireOrg } from "./orgs.js";
import { ulid } from "./ulid.js";
export const TASK_STATUSES = ["backlog", "in_progress", "review", "done"];
function boardPath(orgId) {
    return path.join(requireOrg(orgId), "board.jsonl");
}
export async function readEvents(orgId) {
    const p = boardPath(orgId);
    if (!fs.existsSync(p))
        return [];
    const raw = await fsp.readFile(p, "utf8");
    const out = [];
    for (const line of raw.split("\n")) {
        const trimmed = line.trim();
        if (!trimmed)
            continue;
        try {
            out.push(JSON.parse(trimmed));
        }
        catch {
            // Skip malformed lines rather than failing the whole read.
        }
    }
    return out;
}
export async function appendEvent(orgId, ev) {
    const p = boardPath(orgId);
    await fsp.mkdir(path.dirname(p), { recursive: true });
    await fsp.appendFile(p, JSON.stringify(ev) + "\n", "utf8");
}
/** Fold an event stream into the current task list (spec §3). */
export function foldTasks(events) {
    const tasks = new Map();
    for (const ev of events) {
        switch (ev.type) {
            case "task_created":
                tasks.set(ev.task_id, {
                    id: ev.task_id,
                    title: ev.title,
                    description: ev.description,
                    assignee: ev.assignee,
                    status: "backlog",
                    created_by: ev.created_by,
                    created_at: ev.ts,
                    updated_at: ev.ts,
                    comments: [],
                });
                break;
            case "task_updated": {
                const t = tasks.get(ev.task_id);
                if (!t)
                    break;
                if (ev.patch.title !== undefined)
                    t.title = ev.patch.title;
                if (ev.patch.description !== undefined)
                    t.description = ev.patch.description;
                if (ev.patch.assignee !== undefined)
                    t.assignee = ev.patch.assignee;
                if (ev.patch.status !== undefined)
                    t.status = ev.patch.status;
                t.updated_at = ev.ts;
                break;
            }
            case "task_commented": {
                const t = tasks.get(ev.task_id);
                if (!t)
                    break;
                t.comments.push({ by: ev.by, body: ev.body, ts: ev.ts });
                t.updated_at = ev.ts;
                break;
            }
            case "task_deleted":
                tasks.delete(ev.task_id);
                break;
        }
    }
    return [...tasks.values()];
}
export async function listTasks(orgId, filter) {
    if (filter?.status && !TASK_STATUSES.includes(filter.status)) {
        throw new OrgError("invalid_status", `unknown status ${filter.status}`);
    }
    const events = await readEvents(orgId);
    let tasks = foldTasks(events);
    if (filter?.status)
        tasks = tasks.filter((t) => t.status === filter.status);
    if (filter?.assignee)
        tasks = tasks.filter((t) => t.assignee === filter.assignee);
    tasks.sort((a, b) => a.created_at.localeCompare(b.created_at));
    return tasks;
}
export async function createTask(orgId, args) {
    const taskId = ulid();
    await appendEvent(orgId, {
        type: "task_created",
        ts: new Date().toISOString(),
        task_id: taskId,
        title: args.title,
        description: args.description,
        assignee: args.assignee ?? null,
        created_by: args.by,
    });
    return taskId;
}
export async function updateTask(orgId, args) {
    if (args.patch.status !== undefined && !TASK_STATUSES.includes(args.patch.status)) {
        throw new OrgError("invalid_status", `unknown status ${args.patch.status}`);
    }
    // Existence check: the task must have been created.
    const events = await readEvents(orgId);
    const tasks = foldTasks(events);
    if (!tasks.find((t) => t.id === args.task_id)) {
        throw new OrgError("not_found", `task ${args.task_id} not found`);
    }
    await appendEvent(orgId, {
        type: "task_updated",
        ts: new Date().toISOString(),
        task_id: args.task_id,
        by: args.by,
        patch: args.patch,
    });
}
export async function commentTask(orgId, args) {
    const events = await readEvents(orgId);
    const tasks = foldTasks(events);
    if (!tasks.find((t) => t.id === args.task_id)) {
        throw new OrgError("not_found", `task ${args.task_id} not found`);
    }
    await appendEvent(orgId, {
        type: "task_commented",
        ts: new Date().toISOString(),
        task_id: args.task_id,
        by: args.by,
        body: args.body,
    });
}
//# sourceMappingURL=board.js.map