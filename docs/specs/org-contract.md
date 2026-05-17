# Crawfish Org Contract v1.0

Defines the on-disk schemas, event shapes, and API surfaces shared by `crawfish-lens` (server), `crawfish-dash` (UI), and `crawfish-orgctl` (MCP). All three teammates code against this file. If a field is missing from a real-world case, **SendMessage the lead** rather than extending the contract unilaterally.

---

## 1. Disk layout

Every org lives under `~/.crawfish/orgs/<org_id>/`:

```
~/.crawfish/orgs/<org_id>/
├── org.json              # org config (see §2)
├── board.jsonl           # append-only task event log (see §3)
├── cycles.json           # planning cycles + epics (see §5.5)
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
      "humanity": "agent",             // "agent" | "human" — used by the primary-assignee rule (§3.1)
      "role": "Founder",
      "name": "Casey",                 // display name
      "prompt_file": "members/founder.md",  // relative path; null for humans
      "tools": ["org_fs_*", "board_*", "codebase_*"],  // MCP tool glob patterns; null = all
      "model": "claude-sonnet-4-6",    // null for humans
      "acl": "member"                  // "owner" | "admin" | "member" | "viewer" — see §3.2
    },
    {
      "id": "neal",
      "kind": "human",
      "humanity": "human",
      "role": "Operator",
      "name": "Neal",
      "prompt_file": null,
      "tools": null,
      "model": null,
      "acl": "owner"
    }
  ]
}
```

**Validation rules:**
- `id` matches `/^[a-z0-9_-]{1,32}$/`
- `kind === "agent"` requires `prompt_file` and `model`; `humanity` MUST equal `"agent"`
- `kind === "human"` requires `prompt_file` and `model` to be `null`; `humanity` MUST equal `"human"`
- Members are unique by `id`
- Every org MUST have exactly one member with `acl === "owner"`. Owner cannot be demoted by another member.
- `humanity` defaults to `kind` if absent (backwards compat); new writes MUST set it explicitly.

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
        contributors: string[];
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
  assignee: string | null;          // PRIMARY assignee — see §3.1
  contributors: string[];           // secondary participants — see §3.1
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

### 3.1 Primary-assignee + contributor model

A task has at most one **primary assignee** (`assignee`) and any number of
**contributors** (`contributors: string[]`). The rule resolves who is primary
when both humans and agents touch a task:

1. **`task_created` with a human assignee is sticky.** If a `task_created`
   event sets `assignee` to a member whose `humanity === "human"`, that
   member remains `assignee` until they themselves emit a `task_updated`
   with a different `assignee`.
2. **Agents attached afterward land as contributors.** A later
   `task_updated` patch that would change `assignee` to a member with
   `humanity === "agent"` while the current `assignee` is a human MUST
   instead append that agent's `id` to `contributors` (de-duped). Servers
   reject any client write that tries to overwrite a sticky human assignee
   with an agent — error code `assignee_locked`.
3. **No sticky lock for agent → agent or human → human reassignments.**
   The patch goes through normally; the prior assignee is dropped from
   `assignee` and is NOT auto-added to `contributors`.
4. **Sticky lock is releasable.** The human assignee, an `acl === "owner"`,
   or `acl === "admin"` member may emit a `task_updated` that sets
   `assignee` to an agent (or `null`). The previous human is added to
   `contributors` if not already present.

The fold computes `contributors` by replaying these rules; clients SHOULD
NOT write `contributors` directly except via the documented patches above.
Projected activity entries on assignment carry payload
`{ from: string | null, to: string | null, role: "assignee" | "contributor" }`.

### 3.2 Member ACL (`validateActor`)

Every `BoardEvent` write is gated by `validateActor(org, actor_id, event)`
in `crawfish-lens/src/server/board.ts`. The matrix:

| ACL | Read | Create task | Comment | Update own task | Update any task | Delete task | Edit `org.json` members | Edit cycles |
|---|---|---|---|---|---|---|---|---|
| `owner` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `admin` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (cannot demote owner) | ✓ |
| `member` | ✓ | ✓ | ✓ | ✓ | ✓ (only if listed in `assignee` / `contributors` / `watchers`, or if no assignee) | ✗ | ✗ | ✗ |
| `viewer` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

`validateActor` rejects with HTTP `403 acl_denied` and DOES NOT append to
`board.jsonl`. The rejection itself MAY be journalled to a separate
`audit.jsonl` (out of scope for NOW-W1; reserved).

Agents inherit the ACL of the human who provisioned them via the org
template. Default `acl` for newly-instantiated template members is
`"member"`. Newly-added humans default to `"admin"`.

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

## 5.5 `cycles.json` schema (NOW-W1)

Planning cycles and epics live in a single file per org. The file is read whole, mutated whole, written whole — concurrent writers MUST `If-Match` on the file's mtime (server returns `412 stale` on conflict).

```jsonc
{
  "cycles": [
    {
      "id": "2026-w20",                  // slug, unique within org; matches /^[a-z0-9_-]{1,32}$/
      "name": "Week 20 — RAG cutover",
      "starts_at": "2026-05-18T00:00:00Z",
      "ends_at":   "2026-05-24T23:59:59Z",
      "planned_tokens": 4000000,         // budget for the cycle (sum of intended task budgets); 0 = uncapped
      "spent_tokens": 1234567,           // running total; updated by activity projector on each task_updated with token_spent
      "status": "active"                 // "planned" | "active" | "completed"
    }
  ],
  "epics": [
    {
      "id": "auth-rewrite",              // slug, unique within org
      "title": "Auth rewrite",
      "description": "Replace session-token middleware to satisfy compliance.",
      "owner": "neal",                   // member id; nullable
      "color": "#7C3AED",                // optional UI hint; ui/tokens/globals.css class wins if both set
      "cycle_id": "2026-w20",            // optional — pins epic to a cycle for the swim-lane view
      "status": "active"                 // "planned" | "active" | "completed" | "abandoned"
    }
  ]
}
```

**Validation:**
- At most one `cycle` may have `status === "active"` at a time. Activating another auto-transitions the previous to `"completed"`.
- `starts_at < ends_at`. Cycles MAY overlap (e.g. quarter cycle spanning week cycles) but the active-cycle rule still applies.
- `cycle_id` / `epic_id` on a task MUST refer to a row in this file or be `null`. Server rejects writes referencing unknown ids with `404 unknown_cycle` / `404 unknown_epic`.
- `spent_tokens` is server-derived; clients MUST NOT write it directly. The activity projector recomputes by summing `token_spent` patches per task tagged with the cycle.
- Deleting a cycle/epic does NOT cascade — referencing tasks have their `cycle_id` / `epic_id` cleared by the server in the same write.

`budget_breach` activity events fire when, after a `task_updated` carrying a `token_spent` patch, `cycle.spent_tokens > cycle.planned_tokens` AND the breach was not already recorded for this cycle. Subsequent over-budget writes do NOT re-fire until the cycle is reset (status → `"planned"` or a new cycle is created).

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
| `cycles_list` | `{ org_id }` | `{ tokens_used, cycles, epics }` |
| `cycles_upsert` | `{ org_id, cycles?, epics?, if_match }` | `{ tokens_used, ok, mtime }` |
| `activity_list` | `{ org_id, task_id?, cycle_id?, since? }` | `{ tokens_used, entries: ActivityEntry[] }` |

Errors return `{ tokens_used: 0, error: { code, message } }` with codes drawn from `path_escape | too_large | not_found | invalid_member | invalid_status | acl_denied | assignee_locked | stale | unknown_cycle | unknown_epic`.

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
| `GET` | `/api/orgs/:id/cycles` | returns `cycles.json` whole; ETag = file mtime |
| `PUT` | `/api/orgs/:id/cycles` | replaces `cycles.json`; requires `If-Match: <mtime>` → `412 stale` on mismatch |
| `GET` | `/api/orgs/:id/activity?task_id=&cycle_id=&since=` | flat stream of `ActivityEntry`s across the org (server-derived from `board.jsonl`); SSE variant at `/api/orgs/:id/activity/stream` |
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
