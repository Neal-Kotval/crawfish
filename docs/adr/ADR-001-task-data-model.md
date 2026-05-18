# ADR-001 — Task data model: file-canonical with derived journal (Option C)

- **Status:** Accepted
- **Date:** 2026-05-18
- **Decision owner:** Neal (solo)
- **Supersedes:** Resolves S155 (open since 2026-05-18 mid-day)
- **Related:** GRAND_PLAN.md §3.1 (org templates), §3.2 (issue tracking), §3.14 (orchestration runtime); ROADMAP.md NOW phase Week 1.1.

## Context

Crawfish ships with two task representations that were designed in different sittings:

1. **Org-level board events** at `~/.crawfish/orgs/<orgId>/board.jsonl` — append-only event log, folded into current state by `cli/orgctl/src/board.ts`. Events: `task_created`, `task_updated`, `task_commented`, `task_deleted`, `preflight_attested`. Read/write paths in `cli/orgctl` (MCP tools) and `desktop/lens/src/server/activity.ts` (HTTP/SSE).
2. **Project-level task files** at `<projectRoot>/.crawfish/tasks/<slug>.md` with YAML frontmatter + markdown body. Created externally by the `/crawfish-roadmap` Claude Code skill. Read (never written) by `desktop/dash/src/server/roadmap.ts` for the per-project `ProjectBoard` route.

A codebase audit (2026-05-18, via Explore agent) confirmed that **no application code writes the project-level `.md` files** — only the external skill does. The two boards do not share IDs, schemas, or storage.

The ROADMAP NOW spec (Week 1) was written assuming a single org-level board.jsonl with member ACL. The recent project-centric pivot (S151–S154) introduced the per-project `.md` board. These two designs need to be reconciled before Week 1.1 (cycles + epics) can start.

## Decision

**B1 + Option C.** Concretely:

1. **Keep the org-level board as-is.** `~/.crawfish/orgs/<orgId>/board.jsonl` continues to be the source of truth for cross-project org-level work items. No changes to existing `cli/orgctl/src/board.ts`, `desktop/lens/src/server/activity.ts`, or `desktop/lens/src/server/preflight.ts`.
2. **Project board = `.md` files canonical + new per-project derived journal.** Add `<projectRoot>/.crawfish/board.jsonl` as a new derived event log scoped to a single project. Tasks at `<projectRoot>/.crawfish/tasks/<slug>.md` remain the authoritative state. The journal is a rebuildable index.
3. **Single-writer discipline within the project boundary.** Every code path that creates, updates, deletes, or renames a `.crawfish/tasks/*.md` file must route through a shared writer module that (a) updates the `.md` file and (b) appends an event to `.crawfish/board.jsonl` in one operation. Direct filesystem calls outside this module are forbidden.
4. **Org-level and project-level boards remain separate concepts.** A project task surfacing on the org board (or vice versa) is explicitly out of scope and deferred to Stage 2.
5. **Member ACL is deferred.** The project board has no per-event actor model in Stage 1. The journal records `actor: "local"` or the writing process identity for every event. Real per-user ACL ships when multi-user mode arrives (Stage 2 per GRAND_PLAN §4).

## Consequences

**Positive**
- Week 1.1 unblocked: cycles + epics live in task frontmatter; the new journal carries the activity feed.
- Git-native at the project level: `.md` files diff, blame, merge cleanly.
- No migration of the existing org-board code. The risk of breaking what works is zero.
- The `/crawfish-roadmap` skill keeps generating `.md` files unchanged — it just stops being the *only* writer.
- Disaster recovery is `craw board rebuild`: rebuild `.crawfish/board.jsonl` from `.md` files + git log.

**Negative**
- Two board concepts coexist. A new user has to learn that org tasks ≠ project tasks. Onboarding docs need to explain this.
- The "org-level flow graph" deliverable in GRAND_PLAN §3.12 will eventually need to cross both boards. That bridge is Stage 2 work, not Stage 1.
- Drift risk between `.md` and `.jsonl` is real. Mitigation: single-writer module + rebuild command + tests covering both writes per operation.
- Frontmatter mutations from outside Crawfish (a user editing a `.md` in VS Code) do not emit events. Acceptable for solo founder workflow; documented as a known limitation.

**Neutral**
- `.crawfish/board.jsonl` is a *new* file at the project level. Existing projects pick it up on next write or via `craw board rebuild`. Pre-existing `.md` files are honored.
- The journal event schema borrows event types from `cli/orgctl/src/board.ts` (`task_created`, `task_updated`, etc.) for consistency. Implementations are independent.

## Alternatives considered

- **(A) `.md` files canonical, no journal at all.** Rejected: the Week 1 NOW gate includes an activity feed. Reconstructing one from git log on every read is slow and loses fidelity (multiple frontmatter changes per commit collapse).
- **(B) `.jsonl` canonical at project level; `.md` files as derived export.** Rejected: loses human-editability and the org-fs thesis. Forces every agent to use an MCP tool to file a ticket; today agents write `.md` files directly via filesystem tools.
- **(B2) Move org-board logic to per-project.** Rejected for now: gutting working code with no immediate user-facing win is bad scope discipline. Revisit if the dual-board model becomes a usability problem.
- **(B3) Org as the unit; project board is a filtered view of org board.** Rejected: deletes the project board shipped this week (S152) and re-centralizes data the user just decentralized via the project-centric pivot.

## Implementation outline

1. New module: `cli/projectctl/src/tasks.ts` exposes `createTask`, `updateTask`, `deleteTask`, `renameTask`. Each writes `.md` + appends to `.crawfish/board.jsonl`.
2. Event schema documented in `desktop/lens/src/types/project-board-events.ts` (or equivalent shared location). Event types match the org-board schema where overlap exists.
3. Refactor: every code path identified in the 2026-05-18 audit that writes task-shaped data is routed through `tasks.ts`. The `/crawfish-roadmap` skill is updated to emit events alongside `.md` writes — or, simpler, the rebuild command runs as a post-skill hook.
4. New CLI: `craw board rebuild` walks `.crawfish/tasks/*.md`, emits one `task_created` event per file in mtime order, supplements with git-log derived `task_updated` events. Idempotent.
5. Tests: round-trip — create via writer, fold journal, assert state matches `.md` frontmatter.

## Open questions deferred to a later ADR

- How does the org-level board surface project-level work? (Stage 2, per GRAND_PLAN §4.)
- Per-user ACL: does it live as an event field, a separate `.crawfish/acl.json`, or only in the dash writer layer? (Decide when multi-user mode is in scope.)
- Streaming / SSE on the new project journal: today the dash polls. SSE is a Week 2+ deliverable.
