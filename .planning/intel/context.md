# Context (running notes)

No documents in this ingest set were classified as DOC. This file holds synthesis-time context notes that downstream consumers (gsd-roadmapper) need but that don't belong in requirements/constraints/decisions.

---

## Topic: monorepo pivot — stale path mapping

The active repo is a monorepo (umbrella + sibling submodules). Several ingested docs predate the pivot and reference old top-level repo names. Path mapping for the roadmapper:

- `crawfish-platform/` → `cloud/platform/`
- `crawfish-server/` → `cloud/server/`
- `crawfish-dash/` → `desktop/dash/`
- `crawfish-lens/` → `desktop/lens/`
- `crawfish-web/` → `web/`
- `crawfish-org/`, `crawfish-orgctl/` → `cli/orgctl/`
- `crawfish-opt*`, `crawfish-opt-codebase` → `desktop/opt`, `desktop/opt-codebase`

Docs with stale paths: ROADMAP.md (NOW-slice file lists still use `crawfish-lens/`, `crawfish-dash/`), ROADMAP-MVP.md (throughout), ROADMAP-WAVE3.md (throughout). The current-path docs (ORCHESTRATOR-*) already use `cloud/`, `desktop/`, `cli/`.

source: project memory (project_pivot_agent_orgs.md), CLAUDE.md multi-repo layout, doc cross-comparison

---

## Topic: cross-reference graph (cycle-detection result)

DFS three-color cycle detection was run over the `cross_refs` of the ingested docs. Cycles exist among the companion documents:

- ROADMAP.md ↔ GRAND_PLAN.md (mutual citation)
- ORCHESTRATOR-ONEPAGER.md ↔ ORCHESTRATOR-STAGES.md (mutual citation)
- ORCHESTRATOR-STAGES.md → ORCHESTRATOR-USER-STORIES.md → ORCHESTRATOR-ONEPAGER.md → ORCHESTRATOR-STAGES.md (3-cycle)

**Assessment: benign companion-doc citations, not synthesis-recursion hazards.** These edges are "see also / companion doc" links, not derivation/dependency edges. Extraction in this synthesizer is one-pass-per-document (each doc read once, content extracted independently); there is no transitive traversal that could loop. Max traversal depth was not approached (graph is 7 nodes). Therefore these cycles are recorded as INFO, not as unresolved-blockers. No doc was dropped from synthesis. (If a future ingest introduces ADRs that *supersede each other in a cycle*, that would be a real blocker; this set has none.)

Out-of-set cross_refs (referenced, not ingested): PRODUCT.md, docs/product/{DESIGN,INTEGRATIONS,BRAINSTORM}.md, docs/ops/AGENT-TEAMS.md, ROADMAP-FUNCTIONALITY.md, cloud/server/prisma/schema.prisma, cli/orgctl/src/inbound/*, cli/projectctl/src/{router,stats}.ts. These resolve to source code or un-ingested docs; the roadmapper may pull them if needed.

source: classification cross_refs fields; doc bodies

---

## Topic: orchestrator is a parallel track, not a pivot

All three orchestrator docs and the active ROADMAP.md changelog agree explicitly: the Orchestrator track (O0–O7) is a parallel workstream alongside NOW/NEXT/LATER/LATER², not a replacement of the local-first thesis. The orchestrator is the paid-tier wedge (mid-market, 10–50 eng) that funds the GRAND_PLAN org-OS vision; local-first dash + lens stay MIT and free. This is consistent across docs and is NOT a conflict.

source: ORCHESTRATOR-ONEPAGER.md ("not a pivot away from the Grand Plan"), ORCHESTRATOR-STAGES.md (header), ROADMAP.md (2026-05-22 changelog)
