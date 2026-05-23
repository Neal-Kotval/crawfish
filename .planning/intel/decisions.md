# Decisions (from ADR-classified docs)

No documents in this ingest set were classified as ADR. There are **zero locked decisions** to enforce, and therefore no LOCKED-vs-LOCKED conflicts are possible from this set.

---

## Referenced but NOT ingested (informational — not authoritative here)

Two ADRs are *named* by the ingested docs but are not part of the classification set and so contribute no decisions to synthesis:

- **ADR-001 — board data model.** Referenced by GRAND_PLAN.md §3.2 progress note (2026-05-18): "ratified the data model... per-project file-backed board + JSONL event journal." The ADR document itself is not in the ingest set; `.planning/decisions/` does not exist.
  source: /Users/nealkotval/crawfish/docs/roadmap/GRAND_PLAN.md (mention only)

- **ADR-002 — durable workflow engine choice.** A *future deliverable* (Orchestrator stage O0.1), not yet authored. Intended to compare Temporal / Inngest / Restate and reject BullMQ/pg-boss. Target path `.planning/decisions/ADR-002-orchestrator-workflow-engine.md` does not exist.
  source: /Users/nealkotval/crawfish/docs/roadmap/ORCHESTRATOR-STAGES.md §O0.1, /Users/nealkotval/crawfish/ROADMAP.md §O0

These are recorded for downstream traceability only. The roadmapper should treat the workflow-engine choice as an open decision (see ORCHESTRATOR-STAGES "Open questions before any code"), not a settled one.
