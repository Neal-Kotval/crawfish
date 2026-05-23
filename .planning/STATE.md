# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-22)

**Core value:** A developer can install Crawfish and, within fifteen minutes, have a spawned agent open a real pull request.
**Current focus:** Phase 1 — Standalone Dash MVP

## Current Position

Phase: 1 of 19 (Standalone Dash MVP)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-05-22 — Roadmap created from doc ingest (19 phases across 4 milestones)

Progress: [░░░░░░░░░░] 0%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Local-first MVP (M0, Phases 1–3) is preserved as an earlier shipping milestone, not retired in favor of ROADMAP.md
- Orchestrator (M3, Phases 12–19, O0–O7) is a parallel paid track on top of free MIT substrate; its hard prerequisite is the M1 board (Phase 7)
- All pre-pivot paths translated to monorepo layout (cloud/, desktop/, cli/, web/)

### Roadmap Evolution

- Phase 20 added (2026-05-22): Cloud Issue Ingestion — Linear + GitHub connectors with a Postgres `Issue` model, Linear-Team→Project mapping, OAuth integrations, and a project issues UI in `cloud/platform`. Pulled forward into the cloud-platform line; depends on Phase 2. Design forks resolved: (1) keep auto-provisioned one-workspace-per-user + teams [already shipped in `lib/workspace.ts`]; (2) issues live in a new cloud Postgres `Issue` model; (3) Linear Team → Crawfish Project mapping.

### Pending Todos

None yet.

### Blockers/Concerns

- **OPEN DECISION — ADR-002 (durable workflow engine):** Temporal vs Inngest vs Restate (reject BullMQ/pg-boss) is unresolved. It is an O0 deliverable (Phase 12) and gates the entire Orchestrator track. Recorded as open, not locked.
- **O0 open questions** (must resolve before Phase 12 closes): cloud-server host (AWS/GCP/Fly.io); per-task token-cost ceiling; shared vs separate domain; single vs per-customer GitHub App; craw-authorship policy during curated-only phase; "merge approval" definition vs GitHub branch protection.
- **ADR-001 (board data model)** referenced but not in ingest set; assumed ratified (per-project file-backed board + JSONL event journal).

## Deferred Items

Items carried forward to later milestones:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| GRAND_PLAN | Stage 2 hosted-everything / RL fine-tuning (REQ-stage2-hosted) | Deferred to v2 | Roadmap creation |
| GRAND_PLAN | Stage 3 enterprise / SOC2 / SSO / on-prem (REQ-stage3-enterprise) | Deferred to v2 | Roadmap creation |
| Orchestrator | Marketplace, AI-generated craws, refactor/feature tasks, IDE (REQ-orch-out-of-v1) | Deferred to v2 | Roadmap creation |

## Session Continuity

Last session: 2026-05-22 22:47
Stopped at: Created PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md from doc ingest
Resume file: None
