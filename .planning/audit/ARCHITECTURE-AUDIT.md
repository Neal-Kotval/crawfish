# Crawfish — Architecture Audit (vs. roadmap)

**Date:** 2026-05-22
**Method:** four parallel tier audits (cloud, desktop, cli, cross-cutting) read against `.planning/ROADMAP.md` (20 phases, M0–M3) + `GRAND_PLAN.md` + `ORCHESTRATOR-STAGES.md`. Detail in `CLOUD.md`, `DESKTOP.md`, `CLI.md`, `CROSSCUT.md`.

## Verdict

**Each tier is well-built in isolation. The architecture is NOT yet sound for the roadmap because the tiers do not share a domain model.** The project pivoted from a local-first tool to a cloud agent-org platform, and the core nouns — *org, board, task/issue, member* — forked into parallel, non-reconciled definitions per tier. M1 (Linear-grade board) and all of M3 (orchestrator) assume a single canonical board that does not exist. This is fixable, but it must be settled by ADR **before** more board/orchestrator code lands, or every phase deepens the fork.

This finding implicates the Phase 20 work just completed: adding the cloud Postgres `Issue` model is correct *as a provider-sync mirror*, but it added a fifth task store. It must not be overloaded as the authored board until the reconciliation ADR exists.

## Blockers (must resolve before the dependent phases)

| # | Blocker | Evidence | Blocks |
|---|---|---|---|
| B1 | **Fractured domain model.** 4 board definitions (orgctl `board.jsonl`, dash web board, projectctl `.crawfish/tasks/*.md`, cloud Postgres `Issue`); 3 `TaskStatus` vocabularies (`backlog\|in_progress\|review\|done` vs `todo\|doing\|done\|blocked` vs `open\|closed`); 3 member-role lexicons (`owner\|admin\|member\|viewer` vs `founder\|contributor\|viewer` vs `owner\|contributor`). cloud↔disk join key is the org **name string**, not an id. `org-contract.md` covers only the orgctl/lens board. | CROSSCUT.md, DESKTOP.md, CLI.md | M1 (4–7), M3 (12–19) |
| B2 | **ADR-002 (durable workflow engine) is OPEN** — Temporal vs Inngest vs Restate. It is Phase 12's first success criterion and gates all of M3. Roadmap lists M3 "Not started" when it is actually *blocked*. | CROSSCUT.md, STATE.md | M3 (12–19) |
| B3 | **Cloud has no realtime transport.** `cloud/server` has zero SSE/streaming; Phase 5 (live budget bar) and Phase 15 (per-craw SSE) require it, and ORCHESTRATOR-STAGES wrongly assumes it reuses lens SSE — which lives in `desktop/lens`, a different process/repo. | CLOUD.md | 5, 15 |

## High-severity (resolve before the named phase)

| # | Finding | Blocks |
|---|---|---|
| H1 | **Cloud Prisma schema is a sync-mirror, not a domain model** — no `Cycle`/`Epic`/authored-`Task`/`AcceptanceCriterion`/`TaskLink`/`Activity`/`WorkflowRun`/`AuditLog`. The board features already exist on the *disk* side, not cloud. | M1 (4–7), M3 §O5 |
| H2 | **sqlite vs Postgres unresolved & self-contradictory** — Phase 7 names FTS5 (sqlite-only) while Phase 2 names Neon/Postgres; `labels` is JSON-in-text. No migration story. | 2, 7, 8 |
| H3 | **Three org-creation paths** (cloud `OnboardingFlow` quiz → `createOrg`; cloud `lib/workspace.ts` silent auto-provision; dash first-run wizard → local org) contradict the "one user, one workspace" decision; none seed a board; each hardcodes its own `DEFAULT_AGENTS`. | 1, 2 |
| H4 | **RBAC is membership-only** with two role vocabularies and no role gate on project/integration writes (viewer-can-write hole). Phase 4 is literally "Member ACL." | 4, M3 §O5 |
| H5 | **GitHub inbound implemented twice, incompatibly** — `gh` CLI in `cli/orgctl/src/inbound` vs REST+Clerk in `cloud/server`, with non-aligned external-ref keys; Linear exists only cloud-side. Cross-source dedup is impossible. | 13 (O1 intake) |
| H6 | **No adapter contract** — `docs/specs/adapter-contract.md` is referenced but absent; only `openclaw.ts` exists (cursor/sdk missing); a separate `runtimes/RuntimeProvider` is easily confused with it. | M3 worker runtimes |
| H7 | **Knowledge moat half-built** — RAG core (sqlite-vec + citations) is real, but contextual-bandit router, Tier-1 connectors, knowledge zones, and git-worktree isolation are absent. Phase 8 is ~greenfield. | 8 |

## Medium / hygiene (operational risk for agent-team fanouts)

- **`cli/orgctl/dist` + `dist-test` (24 files) committed** to git with no umbrella `.gitignore` dist rule — asymmetric with submodules (which ignore it correctly). Parallel builds will clobber. (CLI.md)
- **Submodule branch skew**: `desktop/lens` pinned to feature branch `wk5/stage1-now`, `desktop/dash` on `main`. (CROSSCUT.md)
- **`@crawfish/ui` alias mismatch** in dash: `vitest.config.ts` (`../../ui`) vs `vite.config.ts` (`../../../ui`). (CROSSCUT.md)
- **`board.ts` has no file lock** (projectctl has `lock.ts`; orgctl does not); the "single-writer" claim is unenforced; `"escalated"` status isn't in the canonical `TaskStatus`, so budget breaches write a rejected status. (CLI.md, DESKTOP.md)
- **diagnoses `index.ts` explicit `registerRule` registry** is a guaranteed merge-conflict point for the 3-teammate C2.P1.M3 fanout — recommend glob auto-discovery. (DESKTOP.md)
- **Dev auth shim is a full header bypass** in any non-prod env regardless of Clerk config, contradicting its own doc-comment. (CLOUD.md)
- **Stale planning cursor**: STATE.md says "Phase 1/19, 0%" while NOW-W1/W2 board code (cycles, criteria, ACL, budget, FTS5) already landed on the disk side. (CROSSCUT.md)

## Strengths (keep these)

- `cli/orgctl` MCP dispatch: clean prefix-dispatch + spread `*_TOOL_DEFS` + centralized token/error envelope — low-friction to extend for M3.
- Event-sourced disk board with fault-tolerant replay + budget-breach snapshotting.
- Fault-isolated pure-function diagnoses engine.
- Genuine RAG index (sqlite-vec + cosine fallback + byte-range citations).
- Clean `httpError` contract, correct JWT audience separation, device-link squatter defenses, idempotent provider sync, sound contract-test harness.
- `ui/tokens/globals.css` single-source rule genuinely holds — it is the only `.css` in the tree.

## Recommended remediation sequence (before resuming feature work)

1. **ADR-001-REV — Canonical domain model & sync topology** (highest leverage). Decide: one canonical board location (local-canonical / cloud-canonical / federated — three options laid out in DESKTOP.md), one `TaskStatus` enum, one role lexicon, an id-based (not name-based) org join key, and whether the cloud `Issue` is a separate provider-mirror feeding the canonical board or *is* the board. Extend `org-contract.md` to span all tiers. Unblocks B1, H1, H3, H5.
2. **Resolve H2** inside the same ADR or a sibling: sqlite-vs-Postgres and where FTS5 vs Postgres-FTS lives.
3. **ADR-002 — durable workflow engine** (already owed; Phase 12). Unblocks M3 planning. (B2)
4. **ADR — realtime transport for cloud** (SSE/WebSocket; or formally make lens the realtime tier). (B3)
5. **Hygiene pass** (cheap, do anytime): gitignore `cli/orgctl/dist*`, align the dash `@crawfish/ui` alias, reconcile submodule branches, refresh STATE.md cursor.
6. Only then resume M1 board parity on cloud and the Phase 20 nav/onboarding work.

## Bottom line for the roadmap

- **M0 (1–3):** cloud substrate is in good shape for Phase 2; Phase 1/3 are dash-side and tangled with the onboarding fork (H3).
- **M1 (4–7):** **not safely buildable on cloud until B1/H1/H2 are settled** — the board features exist on disk, not cloud, and the model isn't shared.
- **M2 (8–11):** RAG core exists; the rest (bandit/connectors/zones/worktree/GOAP) is largely greenfield — buildable but big.
- **M3 (12–19):** **blocked** on B2 (ADR-002) and depends on B1 + B3 + H5 + H6. Should be reclassified "blocked," not "not started."
