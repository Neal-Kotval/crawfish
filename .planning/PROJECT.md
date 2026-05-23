# Crawfish

## What This Is

Crawfish is a local-first, MIT-licensed platform for running a company on AI agents — "hire your company in fifteen minutes." It is a TypeScript/Node monorepo whose surfaces are a Tauri desktop shell (`desktop/app`) hosting a Linear-grade agent board (`desktop/dash`) and a transcript reader/diagnoses engine (`desktop/lens`), a marketing site (`web`), a signed-in web SPA (`cloud/platform`, React + Vite + Clerk), a platform backend (`cloud/server`, Express + Prisma + Postgres/Neon), and MCP-server CLIs (`cli/orgctl`, `cli/projectctl`). On top of the free local-first substrate sits a paid, cloud-hosted Orchestrator that turns Linear/GitHub issues into CI-verified, checkpoint-gated pull requests for mid-market engineering teams.

## Core Value

A developer can install Crawfish and, within fifteen minutes, have a spawned agent open a real pull request — proven by the launch metric: distinct GitHub usernames who merge a Crawfish-authored PR within 30 days.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. See .planning/REQUIREMENTS.md for full IDs. -->

- [ ] Local-first standalone Dash MVP (one-surface canvas, no auth/backend) → 15-min crawfish.dev-to-PR demo
- [ ] Thin web platform sync layer (Clerk auth, org sync, device-link, read-only online canvas, invite-by-email)
- [ ] MVP verification & hardening pass (Playwright e2e + server contract tests + code-review)
- [ ] Linear-grade agent board: cycles, epics, activity feed, member ACL, acceptance-criteria evidence guard, live token-budget bar, agent preflight self-attestation, capability-matched routing, AI triage, auto-decomposition, linked-task graph, FTS5 structured search
- [ ] Org filesystem + knowledge librarian (LightRAG / `sqlite-vec` / `transformers.js`, contextual-bandit meta-router, Tier-1 connectors)
- [ ] Diagnoses engine + token-discipline optimizer pack (cost-manager, dynamic model switching, 2σ regression alerts)
- [ ] Skills backbone + craws packaging (manifest, defence policy, benchmarked craws) + test-generator/visual-auditor agents
- [ ] Native orchestration runtime (GOAP planner, MVP capabilities 1–3)
- [ ] Hosted Orchestrator (wedge): issue intake → classifier → plan checkpoint → durable execution → CI gate → merge checkpoint → PR-comment loop, with billing, RBAC, audit, analytics, notifications, and public launch

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- GRAND_PLAN Stage 2 (hosted-everything, RL fine-tuning, multi-user analytics) — REQ-stage2-hosted, deferred to a later milestone (m9–m24)
- GRAND_PLAN Stage 3 (compliance tier, SOC2, SSO/SAML/OIDC, on-prem, attestation) — REQ-stage3-enterprise, deferred (m18+)
- Orchestrator v1 exclusions (REQ-orch-out-of-v1): customer-authored craws (until O7), marketplace, AI-generated craws, refactor/feature-class tasks, IDE, local Codespaces, Pilot Protocol, methodology packs
- Deferred-forever in the wedge: Slack-as-execution-surface, per-PR pricing, fully-autonomous PRs without checkpoints
- Anti-goals (all docs): no auto-installation of craws; no per-execution paywall on community craws; no enterprise paywalling of compliance

## Context

- **Monorepo pivot:** Several source docs (ROADMAP-MVP.md, ROADMAP-WAVE3.md, ROADMAP.md NOW-slice file lists) predate the monorepo pivot and use stale top-level paths. Mapping applied throughout this plan: `crawfish-platform/`→`cloud/platform/`, `crawfish-server/`→`cloud/server/`, `crawfish-dash/`→`desktop/dash/`, `crawfish-lens/`→`desktop/lens/`, `crawfish-web/`→`web/`, `crawfish-org*`→`cli/orgctl/`, `crawfish-opt*`→`desktop/opt*`.
- **Orchestrator is a parallel track, not a pivot.** All three orchestrator docs and the ROADMAP.md changelog agree: the hosted Orchestrator (O0–O7) is the paid wedge that funds the GRAND_PLAN org-OS vision; the local-first dash + lens stay MIT and free.
- **Two preserved milestones early.** The local-first Wave 1/Wave 2 MVP and its Wave 3 hardening are preserved as a distinct, earlier-shipping milestone (M0) ahead of the Linear-grade board NOW slice (M1), per explicit user decision. ROADMAP-MVP.md and ROADMAP-WAVE3.md are NOT superseded.
- **Operational decisions asserted by MVP docs:** Auth = Clerk; Backend = Postgres on Neon + Prisma on Vercel (explicitly not Convex); Hosting = Vercel; Dash distribution = GitHub Releases.
- **Substrate reuse:** the Orchestrator reuses ~70% of v0.3 substrate — board (`cli/orgctl/src/board.ts`), router (`cli/projectctl/src/router.ts`), budget (`cli/orgctl/src/budget.ts`), inbound adapters, runtime adapter contract (`desktop/lens/src/adapters/`), Prisma models, Clerk auth, GitHub OAuth, lens SSE.
- **Authoritative root doc:** the hand-written `/Users/nealkotval/crawfish/ROADMAP.md` remains the source of truth for the active build schedule; this `.planning/ROADMAP.md` is the GSD-structured derivation of it and does not replace it.

## Constraints

- **Tech stack**: TypeScript/Node monorepo; Tauri desktop shell; Express + Prisma + Postgres/Neon backend; React + Vite + Clerk SPA — fixed by existing repo layout.
- **License**: Local-first surfaces (dash, lens, skills) are MIT and free; Orchestrator is the paid SaaS surface — core to the product thesis.
- **Build hygiene**: CSS lives only in `ui/tokens/globals.css`; no parallel builds (shared `dist/`); type-check (`tsc --noEmit`) before claiming done — from repo CLAUDE.md.
- **Sequencing**: Pre-pivot MVP milestone ships before the Linear-grade board; Orchestrator track has the NOW slice as a hard prerequisite (board primitives are reused).
- **Verification (NFR)**: MVP hardening requires Playwright e2e green across platform/marketing/dash-web suites + server contract tests green + a code-review doc.

## Key Decisions

<!-- Decisions that constrain future work. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Preserve local-first MVP as an earlier milestone rather than retire it | User chose to keep the proven 15-min-to-PR thesis as a shippable earlier surface; ROADMAP.md precedence-0 would otherwise auto-supersede it | — Pending |
| Orchestrator (O0–O7) runs as a parallel paid track on top of free MIT substrate | Funds the GRAND_PLAN org-OS vision without abandoning local-first thesis | — Pending |
| Durable workflow engine (Temporal vs Inngest vs Restate; reject BullMQ/pg-boss) | Required for crash-safe, idempotent execution; choice deferred to ADR-002 (O0 deliverable) | — Pending (OPEN — ADR-002 not yet authored) |
| Board data model = per-project file-backed board + JSONL event journal | Ratified by ADR-001 (referenced by GRAND_PLAN §3.2; ADR doc not in ingest set) | — Pending |
| Translate all pre-pivot paths to monorepo layout when emitting deliverables | Source docs predate the pivot; avoids building against dead paths | ✓ Good |

---
*Last updated: 2026-05-22 after initial roadmap creation from doc ingest*
