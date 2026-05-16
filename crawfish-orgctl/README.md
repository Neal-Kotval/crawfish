# crawfish-orgctl

> Org control MCP server. Board (append-only task log) + hosted files for Crawfish agent organizations. Sibling to [`crawfish-opt`](https://github.com/Neal-Kotval/crawfish-opt) (browser) and [`crawfish-opt-codebase`](https://github.com/Neal-Kotval/crawfish-opt-codebase) (codebase nav).

## Why

Crawfish v1 (Agent Organizations) gives every running org a tiny on-disk world under `~/.crawfish/orgs/<org_id>/`:

- `board.jsonl` — append-only event log of tasks, updates, comments
- `files/` — a hosted shared FS (≤1 MiB per file)

Agents poke at that world through MCP. This server is the one tool surface, so the same primitives back the dash UI, the lens REST API, and cron-scheduled runs.

Seven tools, all idempotent, all token-priced:

- `board_list_tasks(org_id, status?, assignee?)`
- `board_create_task(org_id, title, description, assignee?, by)`
- `board_update_task(org_id, task_id, by, patch)`
- `board_comment(org_id, task_id, by, body)`
- `org_fs_list(org_id, prefix?)`
- `org_fs_read(org_id, path)`
- `org_fs_write(org_id, path, content)`

See [`docs/specs/org-contract.md`](../docs/specs/org-contract.md) §6 for the binding tool surface.

## Install

```bash
npm install
npm run build
# Point Claude Code / your agent runtime at dist/index.js as an MCP server.
```

## Contract

This server complies with the **crawfish optimizer contract v1.0**:

- Every tool response includes a top-level `tokens_used` field (estimated chars/4 of the serialized payload).
- Tools are idempotent on retry. `board_update_task` with the same patch twice is fine; `org_fs_write` with unchanged content is a no-op.
- Single token sink: org state (board + hosted files). Logs, browser DOM, codebase nav are addressed by separate optimizers.
- Errors return `{ tokens_used: 0, error: { code, message } }` with codes from `{ path_escape, too_large, not_found, invalid_member, invalid_status }`.

## Safety

`org_fs_*` enforces spec §4 path rules:

- Rejects `..` segments, absolute paths, and null bytes.
- Resolved paths must remain under `<org>/files/`.
- 1 MiB cap on reads and writes (→ `too_large`).
- `board.jsonl` is append-only; mutations never rewrite the file.

## Test

```bash
npm test
```

Covers tokens-on-every-response, board create/update/comment round-trips, FS round-trips, path-escape and oversize rejection.

## Status

**v0.1 — initial release.** Flat-architecture orgs only. ACL by tool-glob (§2) is honored by the runtime, not enforced here.
