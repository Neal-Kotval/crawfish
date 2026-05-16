# Crawfish Org Contract v1.0

Defines the on-disk schemas, event shapes, and API surfaces shared by `crawfish-lens` (server), `crawfish-dash` (UI), and `crawfish-orgctl` (MCP). All three teammates code against this file. If a field is missing from a real-world case, **SendMessage the lead** rather than extending the contract unilaterally.

---

## 1. Disk layout

Every org lives under `~/.crawfish/orgs/<org_id>/`:

```
~/.crawfish/orgs/<org_id>/
├── org.json              # org config (see §2)
├── board.jsonl           # append-only task event log (see §3)
├── crons.json            # scheduled runs (see §5)
├── members/              # one .md per agent member (system prompt + tool list)
│   ├── founder.md
│   ├── eng.md
│   └── ...
└── files/                # hosted shared FS (see §4)
    ├── notes.md
    └── ...
```

`<org_id>` is a ULID, lowercase. Templates instantiate by copy: `cp -r <template_dir> ~/.crawfish/orgs/<new_id>/`.

---

## 2. `org.json` schema

```jsonc
{
  "id": "01hxz...",                    // ULID, matches dir name
  "name": "My Startup",
  "template": "startup",               // template slug it was instantiated from
  "created_at": "2026-05-15T19:21:00Z",
  "architecture": "flat",              // v1: always "flat"; future: hierarchical|pipeline|hybrid
  "members": [
    {
      "id": "founder",                 // slug, unique within org
      "kind": "agent",                 // "agent" | "human"
      "role": "Founder",
      "name": "Casey",                 // display name
      "prompt_file": "members/founder.md",  // relative path; null for humans
      "tools": ["org_fs_*", "board_*", "codebase_*"],  // MCP tool glob patterns; null = all
      "model": "claude-sonnet-4-6"     // null for humans
    },
    {
      "id": "neal",
      "kind": "human",
      "role": "Operator",
      "name": "Neal",
      "prompt_file": null,
      "tools": null,
      "model": null
    }
  ]
}
```

**Validation rules:**
- `id` matches `/^[a-z0-9_-]{1,32}$/`
- `kind === "agent"` requires `prompt_file` and `model`
- `kind === "human"` requires both to be `null`
- Members are unique by `id`

---

## 3. `board.jsonl` event shape

Append-only log. Each line is one event. State is derived by folding. SSE tails this file via the existing `crawfish-lens/src/server/tail.ts` pattern.

```ts
type BoardEvent =
  | {
      type: "task_created";
      ts: string;
      task_id: string;
      title: string;
      description: string;
      assignee: string | null;
      created_by: string;
      // Phase 3 additions (all optional on create)
      cycle_id?: string | null;
      epic_id?: string | null;
      labels?: string[];
      watchers?: string[];
    }
  | {
      type: "task_updated";
      ts: string;
      task_id: string;
      by: string;
      patch: Partial<{
        title: string;
        description: string;
        assignee: string | null;
        status: TaskStatus;
        // Phase 3 additions
        cycle_id: string | null;
        epic_id: string | null;
        labels: string[];
        watchers: string[];
        links: TaskLink[];
        // Board-UI extensions (rank for drag-to-rank; budget/activity for
        // client-emitted budget-breach / escalation entries).
        rank: number;
        token_budget: number;
        token_spent: number;
        activity_log: ActivityEntry[];
      }>;
    }
  | { type: "task_commented"; ts: string; task_id: string; by: string; body: string }
  | { type: "task_deleted"; ts: string; task_id: string; by: string };

type TaskStatus = "backlog" | "in_progress" | "review" | "done";

// Phase 3 — task-graph + activity primitives
type TaskLinkKind =
  | "blocks"
  | "depends_on"
  | "duplicates"
  | "relates_to"
  | "subtask_of";

interface TaskLink {
  kind: TaskLinkKind;
  task_id: string;
}

type ActivityKind =
  | "status_changed"
  | "assigned"
  | "commented"
  | "mentioned"
  | "budget_breach"
  | "escalated"
  | "linked"
  | "labeled";

interface ActivityEntry {
  by: string;                  // member id
  at: string;                  // RFC3339 UTC
  kind: ActivityKind;
  payload: Record<string, unknown>;
}
```

- `ts` is RFC3339 UTC.
- `task_id` is a ULID.
- `by` / `assignee` / `created_by` are member `id`s from `org.json`.
- Default `status` for a new task is `"backlog"`.
- Replay is the source of truth; clients SHOULD NOT cache derived state across reloads.

**Folded task shape** (what clients render):

```ts
type Task = {
  id: string;
  title: string;
  description: string;
  assignee: string | null;
  status: TaskStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
  comments: Array<{ by: string; body: string; ts: string }>;
  // Phase 3 — planning + activity (all default to empty/null on fold)
  cycle_id: string | null;
  epic_id: string | null;
  links: TaskLink[];
  labels: string[];
  watchers: string[];
  activity_log: ActivityEntry[];
};
```

`activity_log` is *derived* by the fold: each `task_updated`/`task_commented`
event projects one entry (e.g. `status_changed`, `assigned`, `labeled`,
`linked`, `commented`). The Phase 3 `activity` teammate owns the projection
function; consumers SHOULD treat `activity_log` as read-only.

---

## 4. `files/` — hosted org FS

REST surface (served by `crawfish-lens` at `/api/orgs/:org_id/files`):

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/api/orgs/:org_id/files` | — | `{ entries: Array<{path, kind: "file"\|"dir", size, mtime}> }` (recursive, sorted) |
| `GET` | `/api/orgs/:org_id/files/*path` | — | raw file content (text/plain or octet-stream) |
| `PUT` | `/api/orgs/:org_id/files/*path` | raw body | `{ ok: true, size, mtime }` |
| `DELETE` | `/api/orgs/:org_id/files/*path` | — | `{ ok: true }` |

**Path rules (server MUST enforce):**
- `path` is resolved against `~/.crawfish/orgs/<org_id>/files/`. Any resolved path outside that root → `403 path_escape`.
- Reject `..` segments, absolute paths, and null bytes before resolving.
- Max file size: **1 MiB** in v1. Larger → `413 too_large`.
- Binary files are allowed; UI only previews text.

---

## 5. `crons.json` schema

```jsonc
{
  "crons": [
    {
      "id": "daily-standup",            // slug, unique within org
      "cron": "0 9 * * *",              // standard 5-field cron expression (local TZ)
      "member_id": "founder",           // which agent runs
      "prompt": "Summarize yesterday's board activity and post a standup comment on each in-progress task.",
      "output_to": "board",             // "board" | "files:<path>" | "none"
      "enabled": true,
      "last_run": "2026-05-15T09:00:00Z" // null if never run
    }
  ]
}
```

The cron daemon (`crawfish-lens/src/server/crons.ts`) loads this file, schedules with `node-cron`, and writes outputs back per `output_to`. `last_run` is updated on completion.

---

## 6. `crawfish-orgctl` MCP tool contract

Follows the **crawfish optimizer contract v1.0** (see `crawfish-opt-codebase/README.md`): every response includes `tokens_used`, every tool is idempotent on retry, single token sink (org state).

All tools require an `org_id` argument so one MCP server can serve multiple orgs.

| Tool | Args | Returns |
|---|---|---|
| `board_list_tasks` | `{ org_id, status?, assignee? }` | `{ tokens_used, tasks: Task[] }` |
| `board_create_task` | `{ org_id, title, description, assignee?, by }` | `{ tokens_used, task_id }` |
| `board_update_task` | `{ org_id, task_id, by, patch }` | `{ tokens_used, ok }` |
| `board_comment` | `{ org_id, task_id, by, body }` | `{ tokens_used, ok }` |
| `org_fs_list` | `{ org_id, prefix? }` | `{ tokens_used, entries }` |
| `org_fs_read` | `{ org_id, path }` | `{ tokens_used, content, size, mtime }` |
| `org_fs_write` | `{ org_id, path, content }` | `{ tokens_used, size, mtime }` |

Errors return `{ tokens_used: 0, error: { code, message } }` with codes drawn from `path_escape | too_large | not_found | invalid_member | invalid_status`.

---

## 7. Lens HTTP API additions

Mounted in `crawfish-lens/src/server/index.ts` (lead-only edit).

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/orgs` | list orgs (reads `~/.crawfish/orgs/`) |
| `GET` | `/api/orgs/:id` | returns parsed `org.json` |
| `GET` | `/api/orgs/:id/board` | folded task list |
| `GET` | `/api/orgs/:id/board/stream` | SSE of `BoardEvent`s (tail) |
| `POST` | `/api/orgs/:id/board` | append a `BoardEvent` (server stamps `ts` + `task_id` if missing) |
| `GET/PUT/DELETE` | `/api/orgs/:id/files/*path` | see §4 |
| `GET` | `/api/orgs/:id/crons` | returns `crons.json` |
| `PUT` | `/api/orgs/:id/crons` | replaces `crons.json` |
| `POST` | `/api/orgs/:id/crons/:cron_id/run` | manual trigger |
| `GET` | `/api/orgs/:id/stats?view=dev\|product` | dual analytics (dev = existing session stats; product = board aggregations) |

Dash `crawfish-dash/src/server/*` proxies these or owns its own routes for template instantiation:

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/templates` | list available templates |
| `POST` | `/api/templates/:slug/instantiate` | `{ name } → { org_id }` (copies template dir, allocates ULID, writes `org.json`) |

---

## 8. Open questions (resolve before fanout)

None blocking. Future-extensibility notes:
- `architecture` field exists today but only `"flat"` is honored in v1.
- `members[].tools` glob format intentionally matches MCP tool-name patterns; richer ACL deferred.
- `board.jsonl` schema versioning: not included in v1; first incompatible change adds a `v` field.

---

*Owners:* lead writes this file; teammates read it. Changes after fanout require re-coordination via `SendMessage`.
