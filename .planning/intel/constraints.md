# Constraints (from SPEC-classified docs)

Extracted from docs classified as SPEC. Each constraint carries `source:` for provenance.
Precedence among these SPECs (lower = higher authority): ROADMAP.md (0) > ROADMAP-MVP.md (1) = ROADMAP-WAVE3.md (1) = ORCHESTRATOR-STAGES.md (1).

---

## ROADMAP.md — active build schedule (authoritative, precedence 0)

source: /Users/nealkotval/crawfish/ROADMAP.md
type: protocol (build-schedule contract)
status: authoritative; dated 2026-05-22; manifest_override=true

The active, week-shaped build schedule. Every item is a single named deliverable with files, definition-of-done, and dependency. The doc's own rule: "If a feature is not on this list with a phase and a DoD, it is not being built."

Tracks (constraints on sequencing):
- **NOW (weeks 1–5)** — Linear-grade agent board (P3 fully). Per-week gates:
  - Week 1: cycles + epics + activity feed + member ACL. Files: `crawfish-lens/src/server/{types,cycles,activity,board}.ts`, `crawfish-dash/web/src/routes/Plan.tsx`, `TaskDrawer.tsx`. (Note: doc uses pre-pivot paths `crawfish-lens/`, `crawfish-dash/`.)
  - Week 2: acceptance-criteria evidence guard + token-budget live bar + agent preflight self-attestation. `criteria: [{id, statement, kind: "test"|"manual"|"spec_match", evidence?}]`. `done` transition rejects with `criteria_missing_evidence`. Budget breach at ≥100% emits `budget_breach`, flips task to `escalated`.
  - Week 3: capability-matched routing (lowest `avg_tokens_per_task` with `success_rate > 0.7`, ties → least-loaded) + AI triage column + auto-decomposition planner.
  - Week 4: linked-task graph (5 link kinds: blocks/depends_on/duplicates/relates_to/subtask_of) + FTS5 structured search + external-ref ingestion.
- **NEXT (weeks 6–10)** — RAG indexing (P4.2-finish, `sqlite-vec` + `transformers.js`) + token-discipline optimizer pack + founder-dash polish → Stage-1 demo gate.
- **LATER (weeks 11–16)** — P5: Skills, IDE v0, Codespaces local, LLM Wiki.
- **LATER² (weeks 17–28)** — P6: review, CI, CRDT, web-proxy, hosted opt-in.
- **PARALLEL TRACK (weeks 6–16)** — crawfish.dev marketing/download portal → web dashboard → collaboration → team mode/billing.
- **ORCHESTRATOR TRACK (weeks 6–49, O0–O7)** — hosted orchestrator for mid-market eng teams. Explicitly a parallel track, not a replacement.
- **Stage 2 (m9–m24)** — §4 of GRAND_PLAN: hosted, RL fine-tunes, RBAC.
- **Stage 3 (m18+)** — §5 of GRAND_PLAN: enterprise, SOC2, on-prem.

Datastore/runtime decisions referenced (not ADRs in this set):
- ADR-001 ratified the board data model (per-project file-backed board + JSONL event journal). Referenced by GRAND_PLAN §3.2 progress note; the ADR itself is NOT in the ingest set.
- ADR-002 (durable workflow engine: Temporal vs Inngest vs Restate; reject BullMQ/pg-boss) is an O0.1 deliverable, NOT yet authored. Path `.planning/decisions/ADR-002-orchestrator-workflow-engine.md` does not exist.

---

## ROADMAP.md — Orchestrator track stages (constraints, precedence 0)

source: /Users/nealkotval/crawfish/ROADMAP.md §ORCHESTRATOR TRACK (weeks 6–49)
type: protocol

- Reuses ~70% of v0.3 substrate: board (`cli/orgctl/src/board.ts`), capability router (`cli/projectctl/src/router.ts`), budget primitives (`cli/orgctl/src/budget.ts`), inbound adapters (`cli/orgctl/src/inbound/`), runtime adapter contract (`desktop/lens/src/adapters/`), Prisma org/project models (`cloud/server/prisma/`), Clerk auth, GitHub OAuth, lens SSE.
- Builds new: durable workflow engine, checkpoint workflows, auto-classifier, live team-execution dashboard, PR-comment bot, curated craw library, worktree-isolation utility, Stripe billing, basic RBAC + audit log.
- Local-first NOW/NEXT/LATER slices remain MIT; orchestrator is the paid SaaS surface on top.

---

## ROADMAP-MVP.md — MVP roadmap (precedence 1, PREDATES MONOREPO PIVOT)

source: /Users/nealkotval/crawfish/docs/roadmap/ROADMAP-MVP.md
type: protocol (MVP build contract)
status: STALE — predates pivot; references `crawfish-web/`, `crawfish-dash/`, `crawfish-platform/` (now `web/`, `desktop/dash/`, `cloud/platform/`).

Two-wave MVP:
- **Wave 1 (week 1–2)** — local-first standalone Dash. Explicit assertion: "No platform, no auth, no backend... The dash is the whole product. The platform is dark." DoD: a 15-min recorded video crawfish.dev → PR open. Hides Board/Sessions/Knowledge/Diagnoses; MVP dash has one surface (Canvas).
- **Wave 2 (week 3–4)** — thin web platform sync layer: Clerk auth, org sync API (Postgres + Prisma on Neon/Vercel), device-link, read-only online canvas, invite-by-email. Explicitly NOT: multi-cursor, billing, public session permalinks, org roles/ACL.

Operational decisions asserted: Auth=Clerk; Backend=Postgres on Neon + Prisma on Vercel (explicitly "Not Convex"); Hosting=Vercel; Dash distribution=GitHub Releases.

**CONFLICT FLAG:** Wave-1 "platform is dark" scope and "one-surface dash" directly contradict active ROADMAP.md NOW slice (full Linear-grade board) and the Orchestrator track (platform/auth/backend features). See INGEST-CONFLICTS.md.

---

## ROADMAP-WAVE3.md — verification & hardening plan (precedence 1, STALE PATHS)

source: /Users/nealkotval/crawfish/docs/roadmap/ROADMAP-WAVE3.md
type: nfr (test-coverage + contract-test plan)
status: references pre-pivot surfaces (`crawfish-web`, `crawfish-platform`, `crawfish-dash`, `crawfish-server`).

The trust pass over the two-wave MVP. No new features. Constraints:
- W3.T1 platform Playwright e2e (auth gate, onboarding wizard, OrgPicker, OrgRoute read-only canvas, OrgMembers invite/revoke, `/invites/:code` 3 states + 410 + 404).
- W3.T2 marketing Playwright e2e (platform-detect download, GitHub-release fetch fallback).
- W3.T3 dash-web Playwright e2e (first-run wizard writes org, Canvas reads from disk + drag-persist, OnlineLink device-code, Hire stream).
- W3.T4 crawfish-server contract tests via supertest (health, orgs CRUD+RBAC, invites CRUD+redeem+EMAIL_MISMATCH+expiry, device-link).
- W3.T5 code-review pass over Wave 2 commits → `docs/reviews/REVIEW-WAVE2.md`.
- DoD: `npx playwright test` green in 3 suites; `npm test` green in server; review doc with each severity bucket; `dev.sh` unchanged.

**Dependency note:** Wave 3 is scoped against the Wave 1/Wave 2 MVP surfaces from ROADMAP-MVP.md. If the MVP scope is retired in favor of active ROADMAP.md, the Wave 3 surface list (and its stale paths) must be re-derived.

---

## ORCHESTRATOR-STAGES.md — orchestrator development stages O0–O7 (precedence 1)

source: /Users/nealkotval/crawfish/docs/roadmap/ORCHESTRATOR-STAGES.md
type: protocol (staged implementation plan with exit gates)
status: current (2026-05-22); explicitly a parallel track to NOW/NEXT/LATER/LATER².

Constraints (per-stage exit gates, abbreviated):
- **Pre-stage** — existing NOW slice (Linear-grade board) is a hard prerequisite; v0.3 tag cut, lens+dash tests green.
- **O0 (wk 6–8)** — ADR-002 workflow-engine choice; cloud-server orchestrator skeleton (`cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts`); claude-code worker shim; dep-bumper craw; worktree isolation utility (`cli/orgctl/src/worktree/`); e2e spike script. Gate: spike opens draft PR in CI; ADR-002 merged.
- **O1 (wk 9–14)** — Linear webhook + GitHub Issues poller; plan + pre-merge checkpoint workflows; basic dashboard widget; per-task budget cap; CI gate (GitHub Actions); cancel/retry. Gate: 5 design partners, ≥20 PRs merged, <15min ticket→draft-PR.
- **O2 (wk 15–18)** — test-backfill/lint-cleaner/type-annotator craws; auto-classifier service + per-workspace eval harness; routing-rules UI; allow/deny file-path lists; version pinning; bench fixtures. Gate: classifier precision ≥80%; 10 partners; ≥100 PRs.
- **O3 (wk 19–22)** — multi-craw collab primitive; per-craw SSE; team execution view; replay mode; failure taxonomy (`plan-rejected/ci-failed-after-fixes/budget-exceeded/craw-error/timeout/cancelled-by-user/policy-blocked`); auto-disable on failure spike (>50% in 24h on >5 attempts); manual-takeover detection.
- **O4 (wk 23–26)** — PR-comment bot: GitHub App identity; comment-resolution state machine; per-PR revision (default 5) + token ($10) cap; conflict-with-reviewer detector; out-of-scope detector; auto-respond modes (mention-only default).
- **O5 (wk 27–30)** — Stripe Connect (humans bill, agents free); RBAC (admin/member/viewer + per-resource override); audit-log projection+UI (90-day retention, JSONL export); seat enforcement (402 `seat_limit`); usage metering; monthly budget cap; egress policy; workspace kill switch. Consumes PARALLEL TRACK D weeks 14–16.
- **O6 (wk 31–36)** — onboarding walkthrough; escalation policy; manual-takeover UX; notifications (in-app + email + one-way Slack webhook; PagerDuty/Discord/Teams deferred); support runbooks; status page; on-call; regression alert (2σ).
- **O7 (wk 37–44)** — public signup; customer-authored craw forking; authoring docs + `craw test` CLI; per-workspace craw registry; marketing update; begin GRAND_PLAN Stage 2 prep.

Resourcing assumption: two FTE on orchestrator (1 backend+workflow, 1 frontend+dashboard+cloud-platform). One engineer ×1.8; three ×0.75.

Open questions gating O0 (must resolve before O0 closes): cloud-server host (AWS/GCP/Fly.io); per-task token-cost ceiling; shared vs separate domain; single vs per-customer GitHub App; craw-authorship policy during curated-only phase; "merge approval" definition vs GitHub branch protection.
