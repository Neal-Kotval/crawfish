# Desktop — Architecture Audit

Scope: `desktop/lens/` (transcript reader, REST+SSE, diagnoses engine, runtime
adapters, knowledge RAG) and `desktop/dash/web/` (board, wizards, routes).
Read-only audit against `.planning/ROADMAP.md` (M1 Phases 4-7, M2 Phases 8-11,
M3 Phases 12-19, Phase 20 cloud ingestion) and `docs/roadmap/GRAND_PLAN.md`
(§3.2 board, §3.3/§3.8 adapter moat, §3.9 diagnoses/optimizers, §3.14
orchestration runtime). `desktop/opt*` and `desktop/app` skimmed only.

Date: 2026-05-22. Auditor pass over current `main` working tree.

## Findings

| Severity | Area | Finding | Roadmap phase(s) threatened | Recommendation |
|---|---|---|---|---|
| **BLOCKER** | Board source of truth | Two competing board models with no reconciliation layer. The desktop board is an append-only event journal at `~/.crawfish/orgs/<id>/board.jsonl`, folded into `Task` state in `desktop/lens/src/server/board.ts` (`readAllEvents` → `foldTasks`). The cloud just added a Postgres `Issue` model (`cloud/server/prisma/schema.prisma:152`) scoped to `Project` with `@@unique([projectId, provider, externalId])`, plus an `Integration` token store. Nothing maps `board.jsonl` tasks ↔ Postgres `Issue` rows; `Issue.provider` even reserves a `"native"` value (schema.prisma:156) implying Crawfish-native issues will live in Postgres too. Phase 20's milestone note explicitly calls the cloud `Issue` "the source of truth" while the entire M1 board engine treats `board.jsonl` as the source of truth. | M1 (4-7), Phase 20, M3 intake (13) | Author an ADR deciding ONE canonical board store, or a precise sync contract (which side owns writes, conflict policy, ID mapping). See dedicated subsection below. Do not start Phase 6-7 board features until decided — every feature built on `board.jsonl` deepens the divergence. |
| **HIGH** | Runtime adapter contract | The "adapter contract" promised by GRAND_PLAN §3.8 and CLAUDE.md (C2.P3: `openclaw.ts`, `cursor.ts`, `sdk.ts` against `docs/specs/adapter-contract.md`) does not exist as a shared interface. `desktop/lens/src/adapters/` contains ONLY `openclaw.ts`; no `cursor.ts`, no `sdk.ts`, and no `adapter-contract.md` spec. `openclaw.ts` hand-rolls its own `SessionFile`/`SessionStats` shapes with a comment "returns the same shapes lens already uses for Claude Code" — i.e. it conforms by convention, not by a typed contract. Separately there is a SECOND, unrelated abstraction `desktop/lens/src/runtimes/` (`RuntimeProvider` with `kind`/`run`/`health` — claude-code/claude-api/openai-api/codex) which is for *dispatch*, not transcript ingest. The two are easy to confuse and neither is the clean worker-runtime abstraction M3 needs. | M3 worker runtimes (12-13), §3.8 adapter registry | Write `docs/specs/adapter-contract.md` and extract a typed `TranscriptAdapter` interface from `openclaw.ts` before adding cursor/sdk. Clarify naming: `runtimes/`=dispatch, `adapters/`=ingest; M3 workers need a third concept (execution-in-worktree) that exists in neither. |
| **HIGH** | Agent-filesystem moat (§3.3) | Knowledge substrate is partially built but the on-disk "moat" structure is thin. `desktop/lens/src/knowledge/index.ts` has a real `RagIndex` over `sqlite-vec` (vec0 virtual table + cosine blob fallback, 384-dim) persisting to `~/.crawfish/orgs/<id>/knowledge.sqlite` — solid for Phase 8 retrieval/citations. BUT: no contextual-bandit meta-router (`bandits.sqlite` / `feedback.jsonl` from Phase 8 SC#3) anywhere; no Tier-1 connectors (email/chat/Linear/Jira) — only a generic source ingest; no knowledge "zones" concept; `org-fs.ts` is a flat path-sandboxed file read/write (`safeResolve` + `MAX_BYTES`), not a structured zone model. No git-worktree isolation utility in the desktop tier (roadmap puts it at `cli/orgctl/src/worktree/`, Phase 12). | M2 Phase 8, Phase 12 (worktree) | Treat Phase 8 as mostly greenfield on top of RagIndex: bandit router and connectors are net-new. The RAG core is reusable; the librarian/router/connector layers are not started. |
| **MED** | Dash org model vs cloud org model | The dash first-run wizard (`desktop/dash/web/src/wizards/first-run/index.tsx`) creates a purely LOCAL org: it `POST /api/orgs` to the lens server, writes to `~/crawfish/<name>/` on disk, then routes to `/canvas?org=<name>`. It is Clerk-unaware. The cloud (`cloud/server`) auto-provisions one Org+Workspace per Clerk user and binds Projects 1:1 to GitHub repos. So a user who onboards locally and a user who onboards in the cloud get two unrelated orgs with different identity models (disk slug name vs cuid + Clerk). Phase 2 device-link is the intended bridge but the wizard does not reference it. | Phase 1-2, Phase 20 | Decide whether local-first onboarding remains canonical (cloud mirrors it via device-link) or cloud becomes canonical (dash wizard becomes a cloud-org bootstrapper). Document the identity-mapping (disk org slug ↔ cloud Org cuid) before Phase 20 ships. |
| **MED** | Board concurrency / write model | `board.jsonl` uses append-only events (`appendEvent`, server-stamped ULID + ts) — good for an event log. But `cycles.json` (`server/cycles.ts`) is read-whole/write-whole with `If-Match` mtime optimistic-concurrency (`412 stale`), a DIFFERENT concurrency model from the journal. Two stores, two concurrency disciplines, within the same board. SSE tailing (`board.ts` watcher diffs `lastSize` of the file) is fragile under log rotation/compaction — there is no compaction story for an unbounded `board.jsonl`. | M1 (4-7), scale | Acceptable for MVP. Before multi-user/cloud sync, define journal compaction/snapshotting and unify the concurrency story or document why two models coexist. |
| **MED** | Diagnoses registry merge-conflict risk | The rule registry is sound in shape: `engine.ts` has a `REGISTRY[]` + `registerRule()`; rules are pure `detect(stats, ctx)` functions; one rule failing is caught and does not break the run. BUT registration is centralized in `diagnoses/index.ts` as one explicit `registerRule(...)` line per rule — exactly the file CLAUDE.md flags as a guaranteed merge-conflict point when teammates fan out (C2.P1.M3 lists 8 new rules across 3 teammates). For M2 §3.9 (optimizer pack, more rules) this WILL churn. | M2 Phase 9, agent-team fan-out | Replace explicit registration with directory auto-discovery (glob `rules/*.ts`, each exports a `Rule`) so adding a rule never touches a shared file. This removes the registry from the conflict table entirely. |
| **LOW** | Diagnoses ↔ optimizer coupling | `diagnoses/tool-optimizer-map.ts` is a static tool→optimizer map (also on the CLAUDE.md conflict list). Fine now; for the Phase 9 optimizer pack + dynamic model switching it will need to become data-driven (per-org installed optimizers), not a compile-time constant. | M2 Phase 9 | Plan to move the map behind the org-fs (installed-optimizers manifest) when Phase 9 starts. |
| **LOW** | Adapter coverage vs claims | GRAND_PLAN §3.8 says codex/openai-api are "already partially wired" and openclaw "shipped". In `runtimes/` all four dispatch providers exist; in `adapters/` only openclaw transcript ingest exists. The doc conflates the two layers, overstating ingest coverage. | M3, accuracy of planning | Reconcile the doc with reality; the ingest side is openclaw-only. |

### Strengths

- **Event-sourced board is conceptually right.** `board.jsonl` + `foldTasks`
  is replay-tolerant (skips malformed lines), server-stamps ULIDs/timestamps,
  and snapshots pre-patch state for budget-breach detection
  (`board.ts:286`). The M1 board primitives (acceptance criteria, `budget_breach`
  → `escalated`, `preflight_attested` as a pure activity event) are already
  modeled in the event types (`board.ts:37-105`), matching Phase 5 success
  criteria closely.
- **Diagnoses engine is clean and fault-isolated.** Pure rule functions, a
  try/catch per rule so one bad rule can't sink the batch, and a `RuleContext`
  that lazily supplies expensive reductions (timeline) only to rules that
  need them. The pattern itself is extensible; only the registration file is a
  liability.
- **RAG core is real, not a stub.** `knowledge/index.ts` ships a working
  `sqlite-vec` index with a genuine cosine fallback for ABI mismatches, byte-range
  citations that let the dash deep-link to a slice, and incremental
  per-path re-embedding. This is a strong Phase 8 foundation.
- **SSE hub is simple and correct** (`server/sse.ts`): dead-client pruning on
  write failure, header flush comment, no external dep. Good enough for the
  live activity feed (Phase 4 SC#3) and M3 live dashboard (Phase 15) at MVP scale.
- **Path-sandboxing in org-fs** (`safeResolve`, null-byte binary heuristic,
  `MAX_BYTES`, `413 too_large`) shows security awareness in the file API.

### Top 3 risks for roadmap delivery

1. **Two competing boards (BLOCKER).** The on-disk `board.jsonl` (M1 source of
   truth) and the new cloud Postgres `Issue` model have no reconciliation
   layer, yet Phase 20 declares the cloud `Issue` the source of truth and
   reserves a `"native"` provider. Every M1 board feature (Phases 5-7) built on
   `board.jsonl` widens the gap, and Phase 13 (M3 intake) assumes the cloud
   `Issue` is fed by webhooks. This must be resolved by ADR before more board
   work lands.
2. **No real adapter contract (HIGH).** M3 worker runtimes (Phase 12-13) and
   §3.8's six-runtime registry depend on a clean ingest/execution abstraction.
   Today there is one hand-rolled openclaw adapter conforming by convention, a
   separate `RuntimeProvider` dispatch interface, and no execution-in-worktree
   concept at all. The promised `cursor.ts`/`sdk.ts`/`adapter-contract.md` from
   CLAUDE.md C2.P3 do not exist.
3. **Knowledge moat is half-built (HIGH).** The RAG index is solid but the
   defensible parts of §3.3 — contextual-bandit meta-router, Tier-1 connectors,
   knowledge zones, git-worktree isolation — are entirely absent. Phase 8 is
   closer to greenfield than the roadmap's incremental framing suggests.

### Board duplication: on-disk .crawfish vs cloud Postgres Issue

**There are two boards, and the story is not yet coherent.**

Desktop side (M1 engine, source of truth today):
- `~/.crawfish/orgs/<id>/board.jsonl` — append-only event journal. Events:
  `task_created`, `task_updated`, `budget_breach`, `escalated`,
  `preflight_attested`, etc. (`desktop/lens/src/server/board.ts:37-105`).
- Folded to `Task` state on read (`readAllEvents` → `foldTasks`); tasks carry
  `criteria`, `token_budget/spent`, `cycle_id`, `epic_id`, `links`, `labels`.
- Cycles/epics live separately in `cycles.json` with `If-Match` mtime
  concurrency (`server/cycles.ts`).
- FTS5 search builds a throwaway index FROM `board.jsonl` into
  `~/.crawfish/search/<orgId>.db` (`server/search.ts`) — confirming `board.jsonl`
  is treated as the authoritative input.
- IDs are ULIDs; org id is a disk slug / ULID; identity is local, no auth.

Cloud side (newly added, Phase 20):
- Postgres `Issue` model (`cloud/server/prisma/schema.prisma:152-170`) scoped to
  `Project`, `@@unique([projectId, provider, externalId])`, with
  `provider ∈ {github, linear, native}`, normalized `state`, JSON `labels`,
  `externalKey`, `externalUpdatedAt`, `syncedAt`.
- `Integration` model holds per-org per-provider OAuth tokens.
- `Project` binds 1:1 to a GitHub repo and now carries `linearTeamId/Key`.
- IDs are cuids; org/project provisioned per Clerk user; identity is cloud auth.

**The conflict, concretely:**
- The reserved `provider = "native"` on `Issue` means Crawfish's OWN issues are
  intended to live in Postgres too — directly overlapping `board.jsonl` tasks.
- Phase 20's milestone note says the cloud `Issue` is "the source of truth that
  Phase 13's webhook/poller can later feed," while M1 (Phases 4-7) is entirely
  built against `board.jsonl` as the source of truth.
- There is NO mapping code anywhere: no `Issue.boardEventId`, no
  `Task.externalIssueId`, no sync worker, no conflict policy. The two stores
  have different IDs (ULID vs cuid), different identity (disk slug vs Clerk
  org), different concurrency (append-journal vs row upsert), and different
  containment (org-scoped tasks vs project-scoped issues).

**Assessment:** This is the single biggest architectural risk in the desktop
tier. It is not yet "two competing boards" in the sense of duplicated logic —
the cloud `Issue` is currently an *ingestion mirror* of external trackers — but
the `"native"` provider value and the "source of truth" language in Phase 20
signal an intent to converge them with no contract for how. Recommended action:
an ADR that picks one of three coherent stories and writes it down before any
further M1 board feature lands:
  (a) **Local canonical, cloud mirror** — `board.jsonl` owns all native tasks;
      cloud `Issue` only ever holds external (github/linear) issues; drop the
      `"native"` provider value; device-link pushes a read-only mirror.
  (b) **Cloud canonical** — Postgres `Issue` becomes the board; `board.jsonl`
      degrades to an offline cache that syncs up; the dash first-run wizard
      becomes a cloud-org bootstrapper.
  (c) **Federated** — both are canonical for different scopes with an explicit
      ID-mapping table and a defined conflict-resolution policy.
Until one is chosen, Phases 6-7 (decomposition, links, search) and Phase 13
(intake feeding the cloud `Issue`) are building on an undefined foundation.
