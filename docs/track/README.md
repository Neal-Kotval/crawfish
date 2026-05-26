# Orchestrator track — implementation briefs

Per-surface implementation briefs for the hosted orchestrator MVP. Each `TRACK-N.md`
turns one section of [`../roadmap/ORCHESTRATOR-USER-STORIES.md`](../roadmap/ORCHESTRATOR-USER-STORIES.md)
(§1–§16) into a brief: overview, verbatim user stories, the O0–O7 coding tasks from
[`../../ROADMAP.md`](../../ROADMAP.md) that implement it, and tech-stack considerations.
Section §17 (implementation status) is intentionally not a TRACK file.

`TRACK-N.md` ← §N. The mapping is 1:1 and fixed.

---

## Shipped?

**Status is honest, not aspirational.** The orchestrator track (O0–O7) is *scheduled* in
ROADMAP for weeks 6–44 and has not started — "O0 cannot start until the v0.3 gate is green."
No orchestrator O-stage deliverable has shipped, so every surface is ❌. The **Substrate**
column flags surfaces where reusable code already exists per USER-STORIES §17 (e.g. `budget.ts`,
`stats.ts`, lens SSE, JSONL audit). Substrate is *reuse-ready code*, not a shipped surface —
do not read ◐ as partial delivery of the orchestrator feature.

The recent cloud-board work (Phase 5: token-budget bar, acceptance-criteria evidence guard,
budget-breach escalation) is substrate for §4/§5/§3, not delivery of an orchestrator surface.

| Phase | Surface | O-stages | Shipped? | Substrate |
|---|---|---|---|---|
| [TRACK-1](./TRACK-1.md) | Onboarding & account setup | O0.2, O1.1, O1.2, O2.7, O6.1 | ❌ | ◐ Clerk + GitHub App OAuth, `OrgMember` |
| [TRACK-2](./TRACK-2.md) | Craw library & configuration | O0.4, O2.1–O2.3, O2.7, O2.9, O2.10, O7.2–O7.4 | ❌ | ◐ `craw.yaml` manifest (GRAND_PLAN §3.17) |
| [TRACK-3](./TRACK-3.md) | Issue intake & auto-classification | O1.1, O1.2, O2.4, O2.5, O2.6 | ❌ | ◐ `inbound/{github-issues,notion-pages}.ts`, `triage.ts` |
| [TRACK-4](./TRACK-4.md) | Plan checkpoint (gate 1) | O1.3, O6.2 | ❌ | — |
| [TRACK-5](./TRACK-5.md) | Orchestration & execution | O0.2, O0.3, O0.5, O1.6, O1.8 | ❌ | ◐ `budget.ts`; engine pending ADR-002 |
| [TRACK-6](./TRACK-6.md) | Live team-execution dashboard | O1.5, O3.1–O3.4 | ❌ | ◐ lens REST+SSE, lens replay |
| [TRACK-7](./TRACK-7.md) | CI verification | O1.7, O3 test-gen/visual-auditor | ❌ | ◐ `inbound/github-issues.ts` |
| [TRACK-8](./TRACK-8.md) | PR submission & merge checkpoint (gate 2) | O1.4 | ❌ | ◐ `github-issues.ts` mirror, GitHub merge API |
| [TRACK-9](./TRACK-9.md) | PR-comment loop (auto-respond with budget) | O4.1–O4.8 | ❌ | ◐ JSONL audit substrate |
| [TRACK-10](./TRACK-10.md) | Analytics & cost dashboards | O5.5, O6.10 | ❌ | ◐ `stats.ts`, cost-rollup widgets, GRAND_PLAN §3.6 |
| [TRACK-11](./TRACK-11.md) | Failure handling & escalation | O3.5–O3.8, O6.2, O6.3 | ❌ | ◐ `budget.ts` `budget_breach` |
| [TRACK-12](./TRACK-12.md) | Billing & seats | O5.1, O5.4, O5.5, O5.6 | ❌ | ◐ `OrgMember`; consumes PARALLEL TRACK D |
| [TRACK-13](./TRACK-13.md) | Notifications | O6.4 | ❌ | — |
| [TRACK-14](./TRACK-14.md) | Admin, audit & policy | O2.8, O5.2, O5.3, O5.8, O5.9 | ❌ | ◐ JSONL audit substrate |
| [TRACK-15](./TRACK-15.md) | Eval & quality | O2.5, O2.10, O6.10 | ❌ | ◐ GRAND_PLAN §3.11 cost-manager alerting |
| [TRACK-16](./TRACK-16.md) | Integrations & edge cases | O5.7, O6.5–O6.8 | ❌ | ◐ durable engine (O0.1) for §16.3/§16.4 |

Legend: ✅ shipped · ❌ not started · ◐ reusable substrate exists (not delivery).

---

## Stories that could not be mapped to an O-stage

Flagged as `Gap:` in the individual briefs. These are stories whose required engineering has
no numbered O0–O7 deliverable. Listed per surface.

- **TRACK-1 (Onboarding)**
  - §1.4 — per-repo PR-write eligibility toggle (named as a gap in USER-STORIES §17).
  - §1.5 — CI-provider connect/config UI (O1.7 reads CI status but has no connect screen; CircleCI/GitLab is `[v1.5]`).
  - §1.7 — personal → team workspace conversion + billing re-route (no O-stage; billing is O5.1 but the irreversible conversion flow is uncovered).
- **TRACK-3 (Intake)**
  - §3.3 — manual-override persistence (folded into O2.4 + must land in audit log; not separately numbered).
- **TRACK-7 (CI verification)**
  - §7.6 / §7.7 — test-generator + visual-auditor craws. Promised in ROADMAP prose ("ship as orchestrator craws in stage O3") and the §3.9 row, but **no numbered O3.N deliverable exists** (O3.1–O3.8 are collab/SSE/team-view/replay/failure-handling).
- **TRACK-10 (Analytics)**
  - §10.4 — per-engineer rollup (with the GRAND_PLAN §4.5 aggregates-only privacy constraint).
  - §10.5 — ROI proxy (configurable per-label time-saved).
  - §10.7 — cycle-time comparison (created→eligible→merged vs. human baseline).
  - §10.8 — `[v1.5]` bill forecast.
  - (§10 has no O-stage table of its own; assembled from O5.5 + O6.10 + reused `stats.ts` + reused widgets.)
- **TRACK-11 (Failure handling)**
  - §11.5 — weekly failure digest (overlaps O6.4 digest mode but unnumbered).
  - §11.6 — capability-gap recommendation ("what craw/skill is needed instead" + marketplace link); needs a capability→craw index that does not yet exist.
- **TRACK-12 (Billing)**
  - §12.5 — projected end-of-month cost (v1-scoped, conflicts with §10.8's v1.5 tier; see inconsistencies).
- **TRACK-14 (Admin/audit/policy)**
  - §14.7 — unified, versioned JSON policy bundle. Its constituent settings exist across O1.3/O1.4/O2.7, but the aggregation surface is unbuilt.
- **TRACK-15 (Eval/quality)**
  - §15.4 — custom dry-run benchmark suite (replay customer tickets with all external side-effects suppressed); needs a first-class side-effect-suppressed worker mode.
- **TRACK-16 (Integrations/edge cases)** — weakest 1:1 mapping; the canonical map assigns only operational deliverables (O5.7, O6.5–O6.8). The engineering is unattributed:
  - §16.1 — GitHub-App config-preserving emergency disable. **Unmapped** (kill switch O5.9 pauses dispatch, not the App connection).
  - §16.5 — cross-tracker migration (GitHub Issues ↔ Linear, history-preserving with link-stitching). **Unmapped.**
  - §16.6 — cancellation + 90-day export-then-delete contract. **Unmapped** (O5.1 cancels the subscription; the data-export + deletion contract is unbuilt).
  - §16.2 → O3.8 (manual-takeover detection, conflict variant); §16.3/§16.4 → durable workflow engine (O0.1/O0.2). These *are* mapped, just not in the §16 canonical list.

---

## Inconsistencies between USER-STORIES and ROADMAP

For the lead to reconcile. Surfaced while building the briefs.

1. **Forecast tier conflict.** §12.5 (projected end-of-month cost) is v1-scoped; §10.8 (bill forecast widget) is `[v1.5]`. Both forecast monthly cost from N-day burn. One feature, two tiers — pick one. Recommendation: build once at v1 (§12.5's tier) and let §10.8's "accuracy improves over 30 days" be a refinement.

2. **Test-gen / visual-auditor have no number.** §7.6 promises these as O3 orchestrator craws (ROADMAP prose + §3.9 row "accelerated, ships as orchestrator craws in O3"), but the O3 deliverable table (O3.1–O3.8) is fully consumed by collab/SSE/failure work and contains no entry for them. Either renumber under O3.x or move them under the O2.x craw-library deliverables.

3. **TRACK-16 mapping is operational-only.** The canonical map assigns runbooks, status page, on-call, feedback channel, invite polish (O5.7, O6.5–O6.8) — all correctly placed — but the actual resilience engineering behind §16.1/§16.5/§16.6 lives in no O-stage. The support work presupposes engineering that partly does not exist yet.

4. **Budget cap is split, map lists only half.** §5.6 spans O1.6 (per-task cap) and O5.6 (per-org daily cap), consistent with USER-STORIES §17. But the canonical TRACK-5 map lists only O1.6, so the per-org-cap dependency on TRACK-12 is an implicit cross-track seam. Make it explicit in sequencing.

5. **SLA clock undefined.** §4.7 (4h plan-approval SLA) and §13.6 (24h escalation) do not state whether the timer runs wall-clock or business-hours. Unspecified in both sources; answer once and apply to both, since the escalation machinery (O6.2) and delivery (O6.4) are shared.

---

*Source of record: [`../roadmap/ORCHESTRATOR-USER-STORIES.md`](../roadmap/ORCHESTRATOR-USER-STORIES.md) (last updated 2026-05-22) and [`../../ROADMAP.md`](../../ROADMAP.md) Orchestrator track (O0–O7). Briefs are derived; if a brief and a source disagree, the source wins. Update the source, then re-derive.*
