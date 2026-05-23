## Conflict Detection Report

Mode: new. Precedence: ADR > SPEC > PRD > DOC (per-doc overrides applied). No ADRs in set; zero locked decisions.

### BLOCKERS (0)

None. No LOCKED-vs-LOCKED ADR contradiction (no ADRs ingested), no UNKNOWN/low-confidence classifications, and no synthesis-recursion cycle (the cross-ref cycles present are benign companion-doc citations — see INFO below).

### WARNINGS (2)

[WARNING] Competing product-scope variants: "platform is dark" MVP vs platform-building active roadmap
  Found: ROADMAP-MVP.md (source: /Users/nealkotval/crawfish/docs/roadmap/ROADMAP-MVP.md) asserts a Wave-1 MVP that is local-first standalone — "No platform, no auth, no backend... The dash is the whole product. The platform is dark," and a one-surface dash that hides Board/Sessions/Knowledge/Diagnoses.
  Found: ROADMAP.md (source: /Users/nealkotval/crawfish/ROADMAP.md, dated 2026-05-22, precedence 0) builds the opposite in its NOW slice (full Linear-grade board: cycles, criteria, triage, routing, search) and adds an entire ORCHESTRATOR TRACK (source: /Users/nealkotval/crawfish/docs/roadmap/ORCHESTRATOR-STAGES.md) that is a hosted platform with auth, backend, billing, and RBAC.
  Impact: Both are SPEC-classified. Synthesis cannot silently fold these into one plan without either (a) discarding the local-first standalone-MVP intent, or (b) contradicting the active build schedule. The conflict is a genuine product-direction fork, not noise.
  → Decide whether the Wave-1/Wave-2 standalone MVP is RETIRED in favor of the active ROADMAP.md (recommended — ROADMAP.md is newer and precedence 0; see INFO auto-resolution) OR preserved as a distinct earlier-ship milestone. If retired, mark ROADMAP-MVP.md superseded; if preserved, the roadmapper must sequence it ahead of the NOW slice as a separate variant.

[WARNING] ROADMAP-WAVE3 verification plan is scoped against the contested MVP surfaces
  Found: ROADMAP-WAVE3.md (source: /Users/nealkotval/crawfish/docs/roadmap/ROADMAP-WAVE3.md) tests exactly the Wave 1 / Wave 2 surfaces from ROADMAP-MVP.md (first-run wizard, read-only online canvas, device-link, invite-by-email, the trimmed one-surface dash) using pre-pivot paths (crawfish-web, crawfish-platform, crawfish-dash, crawfish-server).
  Impact: If the Wave-1/Wave-2 MVP is retired (Warning #1), Wave 3's surface list and DoD become orphaned — they verify flows the active roadmap reframes or replaces. Routing this verification plan as-is would generate test work against a scope that may not ship.
  → Resolve Warning #1 first. If the MVP is retired, re-derive Wave 3's targets from the active ROADMAP.md NOW/PARALLEL/ORCHESTRATOR surfaces; if preserved, update Wave 3's paths to the monorepo layout (cloud/platform, cloud/server, desktop/dash, web).

### INFO (3)

[INFO] Auto-resolution available: ROADMAP.md (precedence 0) outranks ROADMAP-MVP.md (precedence 1) on overlapping scope
  Note: Where the two SPECs contradict on the same scope (platform/auth/backend existence, dash surface count), precedence rules make ROADMAP.md the winner — it is precedence 0, manifest-flagged authoritative, and dated 2026-05-22 (newer). This auto-resolution is offered but NOT applied silently: per the ingest instruction, the underlying scope fork is surfaced as a WARNING (above) so the local-first MVP intent is consciously retired rather than dropped. source: ROADMAP.md (precedence 0), ROADMAP-MVP.md (precedence 1).

[INFO] Stale pre-pivot paths in three SPEC docs
  Note: ROADMAP.md (NOW-slice file lists), ROADMAP-MVP.md (throughout), and ROADMAP-WAVE3.md (throughout) reference pre-monorepo-pivot repo names (crawfish-platform/, crawfish-server/, crawfish-dash/, crawfish-lens/, crawfish-web/). Current mapping recorded in intel/context.md → cloud/platform, cloud/server, desktop/dash, desktop/lens, web. The orchestrator docs already use current paths. The roadmapper should translate paths when emitting deliverables. source: intel/context.md (path-mapping table).

[INFO] Cross-reference cycles are benign companion-doc citations
  Note: DFS cycle detection found cycles (ROADMAP.md ↔ GRAND_PLAN.md; ORCHESTRATOR-ONEPAGER.md ↔ ORCHESTRATOR-STAGES.md; STAGES → USER-STORIES → ONEPAGER → STAGES). These are mutual "companion doc" links, not derivation edges. Extraction is one-pass-per-document with no transitive traversal, so no synthesis loop is possible; no document was dropped. Recorded as INFO per the doc-conflict-engine, not as a blocker. source: classification cross_refs; intel/context.md (cross-reference graph).
