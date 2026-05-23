# Synthesis Summary

Single entry point for `gsd-roadmapper`. Produced by `gsd-doc-synthesizer` on 2026-05-22. Mode: new.

## Doc counts by type

- Total ingested: 7
- SPEC: 4 — ROADMAP.md (precedence 0, authoritative), ROADMAP-MVP.md (1), ROADMAP-WAVE3.md (1), ORCHESTRATOR-STAGES.md (1)
- PRD: 3 — GRAND_PLAN.md (2), ORCHESTRATOR-ONEPAGER.md (2), ORCHESTRATOR-USER-STORIES.md (2)
- ADR: 0
- DOC: 0
- All 7 classifications were high-confidence, manifest-overridden. No UNKNOWN/low-confidence docs.

## Decisions locked

- 0 locked decisions. No ADRs in the ingest set.
- ADR-001 (board data model) and ADR-002 (workflow engine) are referenced but not ingested; ADR-002 is an unwritten future deliverable. Treat the workflow-engine choice as OPEN. See intel/decisions.md.

## Requirements extracted

- ~30 requirements across 3 PRDs. IDs:
  - GRAND_PLAN (11): REQ-agent-os-thesis, REQ-tier1-personas, REQ-linear-grade-board, REQ-org-fs-librarian, REQ-knowledge-connectors, REQ-native-orchestration-runtime, REQ-skills-backbone, REQ-craws-packaging, REQ-test-visual-agents, REQ-diagnoses-optimizers, REQ-stage2-hosted, REQ-stage3-enterprise.
  - ORCHESTRATOR-ONEPAGER (4): REQ-orch-wedge-product, REQ-orch-wedge-task, REQ-orch-success-metrics, REQ-orch-out-of-v1.
  - ORCHESTRATOR-USER-STORIES (14, §1–§16): REQ-orch-onboarding, REQ-orch-craw-config, REQ-orch-issue-intake, REQ-orch-plan-checkpoint, REQ-orch-execution, REQ-orch-live-dashboard, REQ-orch-ci-verification, REQ-orch-merge-checkpoint, REQ-orch-pr-comment-loop, REQ-orch-analytics, REQ-orch-failure-handling, REQ-orch-billing-seats, REQ-orch-notifications, REQ-orch-admin-audit-policy, REQ-orch-eval-quality, REQ-orch-integrations-edge.
- Detail in intel/requirements.md.

## Constraints

- 6 constraint blocks across 4 SPECs. Type breakdown:
  - protocol (build-schedule / staged-impl): ROADMAP.md (2 blocks — main schedule + orchestrator track), ROADMAP-MVP.md, ORCHESTRATOR-STAGES.md.
  - nfr (test/contract coverage): ROADMAP-WAVE3.md.
- Detail in intel/constraints.md.

## Context topics

- 3 topics: monorepo pivot stale-path mapping, cross-reference graph (cycle-detection result), orchestrator-is-a-parallel-track confirmation.
- Detail in intel/context.md. (No DOC-classified inputs; these are synthesizer-generated notes.)

## Conflicts

- 0 blockers
- 2 competing-variants (WARNINGS): MVP "platform is dark" scope vs active ROADMAP + Orchestrator; ROADMAP-WAVE3 scoped against the contested MVP surfaces.
- 3 auto-resolved/informational (INFO): precedence resolution offered (ROADMAP.md > ROADMAP-MVP.md); stale paths in 3 docs; benign cross-ref cycles.
- Full detail: /Users/nealkotval/crawfish/.planning/INGEST-CONFLICTS.md

## Per-type intel files

- /Users/nealkotval/crawfish/.planning/intel/decisions.md
- /Users/nealkotval/crawfish/.planning/intel/requirements.md
- /Users/nealkotval/crawfish/.planning/intel/constraints.md
- /Users/nealkotval/crawfish/.planning/intel/context.md

## Routing note for roadmapper

Two WARNINGS require user resolution before routing. The core decision: is the local-first Wave-1/Wave-2 MVP (ROADMAP-MVP.md) RETIRED in favor of the active ROADMAP.md, or PRESERVED as an earlier separate milestone? ROADMAP-WAVE3.md's fate follows from that. Precedence recommends ROADMAP.md wins, but the fork is surfaced for a conscious decision rather than auto-applied.
