# Crawfish — Architecture Docs

Documentation of the system, its concepts, and the roadmap, reflecting the
cloud-canonical direction set in **[ADR-003](../../.planning/decisions/ADR-003-canonical-domain-model.md)**.

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — system architecture: monorepo tiers, the canonical domain model, tier responsibilities under cloud-canonical, auth/RBAC, data flows, persistence, open items.
- **[KEY-CONCEPTS.md](./KEY-CONCEPTS.md)** — glossary of domain, platform, and product concepts (Org, Project, Task vs Issue, Cycle, Epic, roles, Agent, Craw, Orchestrator, the moat, …).
- **[PHASES.md](./PHASES.md)** — per-phase documentation for all 20 roadmap phases, grouped by milestone, with status and the critical path.

Source-of-truth references:
- Decision: `.planning/decisions/ADR-003-canonical-domain-model.md` (cloud-canonical; supersedes ADR-001)
- Audit: `.planning/audit/ARCHITECTURE-AUDIT.md` (tier findings + blockers)
- Plan: `.planning/ROADMAP.md` (the GSD roadmap) · canonical contract: `cloud/server/src/domain/contract.ts`

> **Known drift to reconcile** (flagged during doc authoring): `docs/specs/org-contract.md` is the pre-ADR-003 (disk-canonical) v1 contract and is superseded by `cloud/server/src/domain/contract.ts`; and the Prisma schema still defaults `OrgMember.role` to `"contributor"` (legacy lexicon) — `normalizeRole()` bridges it at runtime, but a schema migration to the `owner|admin|member|viewer` defaults is owed.
