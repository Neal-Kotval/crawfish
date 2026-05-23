# ADR-003 — Canonical Domain Model & Sync Topology

- **Status:** Accepted — Option A (cloud-canonical, desktop = online thin client). Recorded 2026-05-23.
- **Date:** 2026-05-22 (drafted) · 2026-05-23 (decided)
- **Deciders:** Neal Kotval (chose cloud-canonical; delegated the desktop-role sub-decision)
- **Supersedes:** ADR-001 (disk JSONL event journal as the canonical board data model) — see "Supersession" below.
- **Related:** ADR-002 (durable workflow engine — OPEN); H2 (sqlite vs Postgres) resolved here.
- **Source:** `.planning/audit/ARCHITECTURE-AUDIT.md` blocker **B1**

---

## Context

The project pivoted from a local-first tool to a cloud agent-org platform. As features landed per tier, the core domain nouns forked into parallel, non-reconciled definitions (audit B1):

- **4 board/task stores:** `cli/orgctl` `board.jsonl`, `desktop/dash/web` board, `cli/projectctl` `.crawfish/tasks/*.md`, cloud Postgres `Issue`.
- **3 `TaskStatus` vocabularies:** `backlog|in_progress|review|done` · `todo|doing|done|blocked` · `open|closed`; plus orphan `triage`/`escalated` (budget breaches write a status the board rejects).
- **3 role lexicons:** `owner|admin|member|viewer` · `founder|contributor|viewer` · `owner|contributor`.
- **Name-based join key:** cloud↔disk reconcile on the org **name**, which the slug-collision handler can silently break.

M1 (board, Phases 4–7) and all of M3 (orchestrator, 12–19) assume one canonical board that does not exist.

## Decision

**Cloud Postgres is the single canonical source of truth for the org/board domain. The desktop Dash is an online thin client. There is no offline board and no client↔server sync/CRDT layer (that work stays deferred per GRAND_PLAN LATER²).**

- **Canonical store:** Postgres (Neon in prod) owns `Org`, `Project`, `Task`, `Cycle`, `Epic`, `AcceptanceCriterion`, `TaskLink`, `Activity`, `Issue`, `Member`, and (M3) `WorkflowRun`/`AuditLog`.
- **Desktop Dash:** reads/writes the cloud API; renders the board from cloud state. It retains its real local value — running agent execution (Claude Code sessions) and transcript/diagnoses analysis — and **streams results up to the cloud**. It does not own board state.
- **`.crawfish/` on disk:** demoted from "the board" to an **agent working directory** (repo checkout + per-run scratch + git worktree for the code being worked on). Not canonical.
- **Orchestrator (M3):** writes Postgres directly under the durable workflow engine (ADR-002). No journal-replay/materializer needed (this is simpler than the rejected disk-canonical option).
- **Realtime (audit B3):** SSE/WebSocket is **cloud/server's responsibility** (not `desktop/lens`). Required by Phase 5 (live budget bar) and Phase 15 (per-craw SSE).

### Why thin-client over offline-capable
Offline-capable desktop ⇒ dual-canonical ⇒ conflict resolution / CRDT — the work GRAND_PLAN explicitly defers to LATER². Pulling it forward to preserve a local-first promise the product is already leaving is a bad pre-revenue trade. Thin-client is the only coherent cloud architecture with **no sync layer**. (If limited offline is ever needed, add server-authoritative optimistic updates — last-write-wins — without changing this canonical decision; never CRDT.)

## Canonical model (ratified)

1. **Identity.** Stable opaque ids (cuid) on every entity. Org **name/slug is a mutable label, never a join key** — all joins key on `id`. (Fixes the slug-collision break.)
2. **`TaskStatus` (single enum):** `triage → backlog → in_progress → in_review → blocked → done → canceled`. `escalated` is an **orthogonal boolean flag**, not a status (fixes the budget-breach-writes-rejected-status bug). Mapping: orgctl `review→in_review`; dash `todo→backlog`, `doing→in_progress`.
3. **`Task` vs `Issue` are distinct.** `Task` = authored board work item (cycles/epics/criteria/links attach here). `Issue` = external provider record (GitHub/Linear), read-mostly, synced (Phase 20). An `Issue` may be linked to or *promoted into* a `Task` (which creates a real Task row); the `Issue.provider="native"` value is **retired**.
4. **Role lexicon:** `owner | admin | member | viewer`. Mapping: `founder→owner`, `contributor→member`, invite `owner→owner`. **Write-gate added:** board/project/integration mutations require ≥ `member`; settings/billing require `admin`/`owner`. (Closes the viewer-can-write hole; substrate for Phase 4 "Member ACL.")
5. **Single cross-tier contract.** `docs/specs/org-contract.md` is extended to define these canonical entities for all tiers, and TypeScript types are shared via a `@crawfish/contracts` package (or codegen) so cloud + cli + desktop stop redefining the nouns.

## Sub-decision (H2) — sqlite vs Postgres / FTS

Canonical store is **Postgres** (Neon). Search uses **Postgres full-text search**; Phase 7's "FTS5" requirement is reinterpreted as "structured full-text search on the canonical store" (Postgres FTS), not literal sqlite FTS5. Local sqlite in lens is retained only for local transcript/diagnoses analysis, not the board.

## Supersession of ADR-001

ADR-001 ("per-project file-backed board + JSONL event journal" as the canonical board data model) is **superseded**. The event journal/disk board is no longer canonical; it is at most a local execution artifact. PROJECT.md Key Decisions and STATE.md are updated accordingly.

## M0 redefinition (consequence)

The local-first MVP (M0, Phases 1–3, preserved at ingest with "the platform is dark") is **redefined as a cloud-first onboarding**: sign in (Clerk/GitHub) → auto-provisioned workspace → import a repo → hire an agent that opens a real PR — in under 15 minutes, no card, MIT. The "local-first / platform-dark / dash-is-the-whole-product" framing from `ROADMAP-MVP.md` Wave 1 is retired. (This re-resolves the earlier ingest fork toward the active cloud roadmap.)

## Moat reframe (consequence)

GRAND_PLAN §3.3 names the on-disk *agent filesystem* as the moat. Under cloud-canonical that is no longer the defensible core. **The moat is reframed to the hosted org-OS**: capability-routed agent organization, durable orchestration, the knowledge/RAG substrate as a cloud service, and the accumulated org/board/eval data. The filesystem becomes an execution detail. §3.3 of GRAND_PLAN should be rewritten to match (follow-up).

## Consequences

**Positive**
- One source of truth; no split-brain, no CRDT. M1 board + M3 orchestrator both build on Postgres directly. Phase 20's cloud `Issue` work fits with zero rework. Realtime/RBAC/audit have a clear home (cloud/server). Onboarding collapses to one cloud path.

**Negative / costs (accepted)**
- **Significant desktop refactor:** lens/orgctl/projectctl board ownership moves to cloud; the dash board becomes a cloud-API client; lens board endpoints are deprecated or proxied; the dash first-run org quiz is removed (onboarding is cloud). Part of the shipped NOW-W1..W5 disk-board work is reworked.
- **Desktop requires connectivity** for board operations (no offline board).
- **Marketing/positioning change:** "local-first" is no longer the pitch; the moat narrative shifts to the hosted org-OS.

## Migration implications (per tier)

- **cloud/server:** gains the full domain model (`Cycle`/`Epic`/`Task`/`AcceptanceCriterion`/`TaskLink`/`Activity` + roles + write-gates + SSE). This becomes the home of M1 board work (audit H1 closed here).
- **desktop/dash:** board routes read/write the cloud API; remove the first-run org quiz; keep local execution + trace UI.
- **desktop/lens:** retain transcript reader + diagnoses over local logs; deprecate/proxy its board+cycles endpoints; post findings to cloud.
- **cli/orgctl + projectctl:** `board.jsonl`/`.crawfish/tasks` writers become cloud-API clients or are repurposed to execution scratch; unify GitHub inbound on the cloud path (audit H5); add Linear (done).
- **Contracts:** author `@crawfish/contracts` + extend `org-contract.md`.

## Follow-ups

- ADR-002 (durable workflow engine) still owed; it now drives Postgres state transitions.
- Reclassify M3 as "blocked on ADR-002"; refresh the stale STATE.md cursor.
- Rewrite GRAND_PLAN §3.3 (moat) and `ROADMAP-MVP.md` Wave 1 (local-first retired).
- Resume the paused Phase 20 Board+Projects nav + onboarding reconciliation — now unambiguously cloud-side.

## What this unblocks

B1, H1, H2, H3, H4, H5 — and clears the path to build M1 board on cloud and resume the paused Phase 20 UI/onboarding work.
