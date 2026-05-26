# TRACK-14 — Admin, audit & policy

## Overview
The governance surface: an append-only audit log of every governance-relevant action, RBAC roles with a documented permission matrix, a workspace-wide kill switch, per-craw file-path allow/deny lists, per-craw/per-org network-egress policy, and a versioned policy bundle. Primary personas: SEC (audit, allowlists, egress), PLAT (RBAC), VPE (kill switch, policy bundle). Cross-cuts everything — it constrains what craws may touch (file paths, network) and records what humans and craws did. The audit store reuses the shipped JSONL substrate; the projection + UI are the new work.
Source: ORCHESTRATOR-USER-STORIES.md §14.

---

## User stories

14.1 **[SEC]** Every governance-relevant action is written to an immutable audit log: member added/removed, role changed, craw installed, policy edited, budget changed, manual task takeover. *AC: log is append-only; exportable as JSONL; uses existing JSONL substrate.*

14.2 **[SEC]** Filter the audit log by actor, action type, time window, and resource. *AC: 90-day retention default; configurable per workspace; older data exported and purged.*

14.3 **[PLAT]** RBAC: assign roles (admin, member, viewer); each role has a documented permission matrix. *AC: matrix shipped as docs; admin can override per-resource.*

14.4 **[VPE]** Set a kill-switch policy: pause all craw activity workspace-wide. *AC: pause is reversible; in-flight tasks complete; new dispatches queue.*

14.5 **[SEC]** Configure a per-craw allow/deny list of file paths (e.g., the lint-craw cannot touch `/secrets/` or `/migrations/`). *AC: enforced at the worktree mount level; violations block before commit.*

14.6 **[SEC]** Configure a per-craw allow list of network egress destinations (default: GitHub + LLM provider only). *AC: matches GRAND_PLAN §3.16 defence-toolcall pattern.*

14.7 **[VPE]** Configure a policy bundle per workspace: required reviewer count, allowed labels, max diff size for auto-approval. *AC: policy bundle is JSON; editable in dashboard; versioned with audit trail.*

14.8 **[deferred → v2]** SSO, SAML, OIDC, custom retention policies, data residency.

---

## Coding tasks (from ROADMAP.md)

- **O2.8** — Per-craw file-path allow/deny lists (dashboard + worker, defence-toolcall pattern from GRAND_PLAN §3.16) — implements §14.5 (worktree-mount enforcement, block before commit).
- **O5.2** — RBAC roles + permission matrix (`cloud/server/src/auth/rbac.ts` + `docs/orchestrator/rbac-matrix.md`) — implements §14.3 (admin/member/viewer, matrix shipped as docs, per-resource override).
- **O5.3** — Audit log projection + UI (90-day default retention) (`cloud/server/src/audit/{index,query}.ts` + `cloud/platform/src/pages/AuditLog.tsx`) — implements §14.1 (append-only, the six action types, JSONL export) and §14.2 (filter by actor/action/time/resource, 90-day default, export-and-purge).
- **O5.8** — Per-craw + per-org network egress policy (`cloud/server/src/policy/egress.ts`) — implements §14.6 (default GitHub + LLM provider only).
- **O5.9** — Workspace-wide kill switch (dashboard + workflow) — implements §14.4 (reversible pause, in-flight completes, new dispatches queue).
  - Reuses: existing JSONL audit substrate — directly cited in §14.1 AC; the store is shipped, the projection + UI is the new work (USER-STORIES §17, §14.1).

Gap / flag: §14.7 **policy bundle** (JSON: required reviewer count, allowed labels, max diff size for auto-approval; versioned with audit trail) has no numbered deliverable. Its constituent settings live across surfaces — required reviewer count is §8.5 (O1.4), max-diff-for-auto-approval is §4.5/§4.6 (O1.3), allowed labels is routing (O2.7) — but the *unified, versioned JSON policy bundle* surface is unbuilt. Lead should assign or confirm it's an aggregation view over existing settings.

Note: §14.8 SSO/SAML/OIDC + custom retention + data residency is `[deferred → v2]`; ROADMAP confirms SSO is Stage 3. No O-stage.

---

## Tech stack considerations

- §14.1 audit log is append-only and reuses the shipped JSONL substrate — the store exists; O5.3 builds the *projection* (queryable index) + UI. Append-only is the integrity guarantee: the projection may be rebuilt, but the JSONL is the immutable record. Every other surface's governance events (member changes, craw installs, policy edits, takeovers, PR-bot revisions §9.7) write here — one trail.
- §14.5 file-path allow/deny is enforced "at the worktree mount level, violations block before commit" (O2.8) — this is a worktree-isolation concern (TRACK-5, O0.5) plus the GRAND_PLAN §3.16 defence-toolcall pattern, not a post-hoc diff check. Enforcement before commit means the worker rejects a write to `/secrets/` at the filesystem boundary, not at PR time.
- §14.6 egress allowlist (default: GitHub + LLM provider only) also follows the §3.16 defence-toolcall pattern; per-craw and per-org scoping (O5.8) means a forked craw (TRACK-2 §2.7) cannot widen its egress beyond its org policy. Network policy and file-path policy are two halves of the same craw-containment story — keep them in one policy model.
- §14.3 RBAC ships the permission matrix as docs (`rbac-matrix.md`) with per-resource admin override; the matrix is authoritative for what each role may do across every surface. Seat/role assignment (TRACK-1 §1.2, TRACK-12 seats) reads from this — RBAC and seat-billing share the `OrgMember` model but answer different questions (may-do vs. is-billable).
- §14.4 kill switch is the broadest pause: workspace-wide, reversible, in-flight completes, new dispatches queue — the same pause mechanic as budget caps (TRACK-5/12) but at maximum scope. It must be reachable fast (SEC/VPE emergency action) and itself audited (§14.1).
- §14.2 retention is 90-day default, configurable, with export-and-purge of older data; the purge must not break the append-only guarantee — purge is an archival export + tombstone, not an in-place delete. Custom retention policies are §14.8 deferred, so v1 ships the 90-day default + a single configurable window only.
