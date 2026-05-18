# Crawfish Project Folder — Design

Date: 2026-05-18
Status: Draft, pending implementation plan

## Summary

Define `.crawfish/` — a checked-in folder convention that lives at the root of any repo a Crawfish user wants the Crawfish dashboard to render. The folder holds a small set of derived markdown files (memory, context, roadmap, decisions, activity) plus a machine-readable manifest (`index.json`). A CLI engine keeps the files fresh; an MCP server gives Claude an intent-based write surface; Claude Code hooks handle automatic upkeep. The dashboard (Dash desktop + the web platform) renders a project tab set directly from these files.

This makes a "project" a real artifact in the user's repo rather than an opaque platform-DB row. The Crawfish platform DB only stores which org owns which project; everything else lives in the repo.

## Goals

- Give the Crawfish dashboard a per-project on-disk shape, parallel to the existing per-org shape at `~/.crawfish/orgs/<id>/`.
- Make derived project docs (roadmap, memory, decisions, etc.) stop flooding the root of a user's repo by centralizing them under `.crawfish/`.
- Keep the user's repo the source of truth: no required server-side database for project content.
- Provide three frontends (CLI, MCP, Claude Code hooks) over one engine so the format works for Claude users, CI, and human teammates without Claude.

## Non-goals

- Replacing the org folder format at `~/.crawfish/orgs/<id>/`.
- Multi-project monorepos (one `.crawfish/` per repo root in v1).
- A watcher daemon (deferred; the CLI is the canonical engine).
- Custom renderers / plugins.
- Storing or modifying session transcripts (Claude Code owns that).
- Dogfooding the format on the Crawfish monorepo itself — the monorepo is the product, not a consumer of it.

## Folder shape

```
.crawfish/
├── index.json         # manifest: schema version, file list, last-updated, source-hash map
├── memory.md          # auto-mem rollup (deduped, redacted, scoped to this project)
├── context.md         # token usage, savings %, hot files, expensive tools
├── roadmap.md         # rendered from .planning/ or ROADMAP.md or GH Projects
├── decisions.md       # append-only ADR log (Claude flags via MCP, user edits)
└── activity.md        # rolling per-session journal (last N, trimmed)
```

`index.json` is load-bearing. It stores the source→derived dependency map that powers "if X updated, update Y" semantics:

```json
{
  "schema": "crawfish-project/v1",
  "files": {
    "roadmap.md": {
      "sources": [".planning/**/PLAN.md", "ROADMAP.md"],
      "hash": "sha256:..."
    },
    "memory.md": {
      "sources": ["~/.claude/projects/<repo>/memory/**"],
      "hash": "sha256:..."
    }
  },
  "last_updated": "2026-05-18T13:15:00Z"
}
```

The dashboard reads `index.json` first. If the schema version doesn't match its parser, it shows an "upgrade your `.crawfish/` folder" banner instead of guessing. Unknown files are passed through as raw markdown tabs.

`activity.md` is included in v1 but marked opt-in via `index.json.files["activity.md"].enabled = false` by default — it has high overlap with `memory.md` and can earn its own file in a later cut.

## The three surfaces

All three call the same engine: a Node package under `crawfish-projectctl/` (sibling to the existing `crawfish-orgctl/`), exposing both a CLI binary and a library import.

### CLI — `crawfish project <verb>`

| Verb | What it does | Typical caller |
|---|---|---|
| `init` | Creates `.crawfish/` with stub files + `index.json`, registers default sources. | One-time per repo. |
| `refresh [file...]` | Re-derives one or all files from their declared sources; no-op if source hashes unchanged. | Hooks, CI, manual. |
| `memory append <text>` | Adds a deduped memory entry. | MCP. |
| `decision add <title> <body>` | Appends an ADR entry. | MCP. |
| `activity record` | Reads `$CLAUDE_TRANSCRIPT_PATH` (or stdin), appends a session entry, trims to last N. | `SessionEnd` hook. |
| `status` | Prints which files are stale (source hash differs). | CI / quick check. |
| `doctor` | Validates schema, finds missing sources, flags stale entries >30 days. | Manual. |
| `install-hooks` / `uninstall-hooks` | Writes/removes the three hook entries in `.claude/settings.json`. | One-time, opt-in. |

`refresh` is the workhorse: it reads `index.json`, walks each derived file's source globs, computes a stable hash, and only re-renders files whose source hash has changed. Concurrent invocations coordinate through a `.crawfish/.lock` lockfile; second invocation within `--debounce <duration>` no-ops.

A redaction pass (API-key/token regex + a configurable `.crawfish/.redact` allow/denylist) runs on every write. Default-on.

### MCP — `crawfish-projectctl`

Five tools, all thin wrappers over the CLI:

- `project_refresh(files?)` — wraps `refresh`.
- `project_memory_append(text, tags?)` — wraps `memory append`.
- `project_decision_add(title, body, links?)` — wraps `decision add`.
- `project_status()` — returns the stale-file list as structured data.
- `project_read(file)` — returns one file's content so Claude can cite it back without re-reading from the filesystem.

No write-arbitrary-file tool. Every write goes through a verb so the schema stays enforceable.

### Hooks — three of them, opt-in via `crawfish project install-hooks`

```json
{
  "hooks": {
    "SessionEnd":       [{ "command": "crawfish project activity record" }],
    "PostToolUse":      [{ "matcher": "Edit|Write", "command": "crawfish project refresh --debounce 30s" }],
    "UserPromptSubmit": [{ "command": "crawfish project refresh memory.md --quiet" }]
  }
}
```

- `SessionEnd` journals the session into `activity.md`.
- `PostToolUse` on Edit/Write does a debounced refresh so `roadmap.md` re-renders when source files change.
- `UserPromptSubmit` does a cheap memory.md refresh so the next turn sees latest auto-mem.

Hooks are not required. The CLI works without them; they just remove the "Claude forgot to call MCP" failure mode.

## How it fits the org/project model

```
Org     → ~/.crawfish/orgs/<id>/        (existing, unchanged)
Project → <repo>/.crawfish/             (this design)
```

An org has many projects; a project belongs to exactly one org. The platform already imports GitHub repos as projects (per the GitHub-login-and-import spec). This design defines what that import produces and maintains:

1. User clicks "Import repo" in Dash → Dash clones locally (per existing spec).
2. Dash runs `crawfish project init` inside the clone. The `.crawfish/` folder lands, gets committed on a branch, opens a PR for the user to review.
3. From then on, hooks (if installed) keep the folder fresh; the platform reads it.

### Dashboard consumption

The platform and Dash gain a Project view that renders directly from `.crawfish/`:

| Dashboard tab | Source file |
|---|---|
| Memory | `.crawfish/memory.md` |
| Context | `.crawfish/context.md` |
| Roadmap | `.crawfish/roadmap.md` (+ `.planning/` if present) |
| Decisions | `.crawfish/decisions.md` |
| Activity | `.crawfish/activity.md` |

Two ingestion modes:

- **Local (Dash).** Walks the cloned repo on disk. No sync layer.
- **Remote (platform web).** Reads via GitHub API on `main` (raw contents). Always one commit behind; acceptable because these are derived docs, not live state.

### Where things live — the clean line

| Concern | Lives in |
|---|---|
| Project memory, context, roadmap, decisions, activity | `<repo>/.crawfish/` (this design) |
| Org membership, boards, cycles, members, agents, files | `~/.crawfish/orgs/<id>/` (existing) |
| Which project belongs to which org | Platform DB (one row per project) |
| Auth / Clerk / GitHub OAuth | Platform DB (existing) |
| Session transcripts | `~/.claude/projects/...` (Claude Code; not moved) |

Nothing here touches the org folder format. The two formats are parallel.

## Edge cases and risks

- **Schema versioning.** `index.json.schema` is a hard pin. v1 lock means breaking changes after launch hurt. The platform parser pins by schema version and renders an "upgrade your `.crawfish/` folder" banner when it doesn't match.
- **Concurrent hook invocations.** PostToolUse on Edit/Write fires constantly. The `--debounce 30s` flag uses `.crawfish/.lock`; second invocation within the window no-ops.
- **Merge conflicts in derived files.** Two teammates running hooks at once will conflict on the same `.crawfish/*.md`. The CLI writes through `.crawfish/.staging/` and only promotes to the final path when content actually differs from HEAD. A `.gitattributes` rule marks the six derived files as `merge=ours` so we always take the local refresh and trust the next run to converge — same pattern lockfiles use.
- **Secret leakage in derived docs.** `memory.md` could pull sensitive snippets from auto-mem. The redaction pass runs by default; users can extend `.crawfish/.redact` with custom patterns.
- **Non-Claude users.** The CLI doesn't depend on Claude. Teammates using Cursor or plain git can run `crawfish project refresh` manually or wire it into pre-commit. The format is the contract; Claude is one client.
- **Multi-project monorepos.** Out of scope for v1. If users hit this, a v2 extension adds `.crawfish/projects/<name>/`.

## Build order

Five small slices. Slice 1 is independently shippable; slices 2–5 layer on.

**Slice 1 — engine + CLI (~2 days).**
- `crawfish-projectctl/` package, mirrors `crawfish-orgctl/` layout.
- Verbs: `init`, `refresh`, `status`, `doctor`.
- Renderers for `memory.md`, `roadmap.md`, `context.md`, `decisions.md`, `activity.md`, and `index.json`.
- Source-hash-based dirty detection. Redaction pass. Lockfile-based debounce.
- Vitest fixtures: a fake repo with `.planning/`, run `refresh`, assert outputs.

**Slice 2 — MCP wrapper (~½ day).**
- `crawfish-projectctl/mcp/server.ts` exposes the five tools as shell-outs to the CLI.
- Reuse the boundary-test pattern from `crawfish-orgctl/`.

**Slice 3 — hooks preset (~½ day).**
- `crawfish project install-hooks` / `uninstall-hooks` verbs.
- Document the debounce semantics and how to disable specific hooks.

**Slice 4 — platform consumers (~2 days, parallel-safe after schema lock).**
- Dash gains a Project view that reads `.crawfish/` from disk.
- Platform gains a Project view that reads `.crawfish/` via the GitHub API on `main`.
- Both render the same five-tab set.

**Slice 5 — reference fixtures (~½ day).**
- `crawfish-projectctl/fixtures/gsd-project/` — synthetic repo with `.planning/` proving `roadmap.md` derivation from GSD.
- `crawfish-projectctl/fixtures/plain-readme-project/` — synthetic repo with just `ROADMAP.md`, proving the fallback path.
- These become the integration-test corpus and the demo data for the platform's Project view.

Total: ~5.5 working days.

## Out of scope for v1

Listed explicitly to prevent drift:

- Multi-project monorepos.
- Watcher daemon.
- Cross-project rollups in the org dashboard.
- Custom renderers / plugins.
- Session transcript storage or modification.
- Running the format on the Crawfish monorepo itself.

## Open questions

- Single binary vs. two: today there's `crawfish-orgctl`; this adds `crawfish-projectctl`. Long-term they should merge into a single `crawfish` CLI with `crawfish org ...` and `crawfish project ...` subcommands. Recommend keeping them separate through v1 and merging in a later pass once both are stable.
- Cadence for `activity.md` trimming: keep last 50 sessions vs. last 30 days. Pick during slice 1 based on what the renderer feels like.
