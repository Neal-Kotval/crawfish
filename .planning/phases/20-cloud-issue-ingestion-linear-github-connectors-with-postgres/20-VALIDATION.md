---
phase: 20
slug: cloud-issue-ingestion-linear-github-connectors-with-postgres
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-22
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Targets `cloud/server` (Express + Prisma) and the `cloud/platform` SPA.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest 1.x + supertest (server); existing harness force-resets the DB via `prisma db push --force-reset` reading `schema.prisma` |
| **Config file** | `cloud/server` package (`test: vitest run`) — confirm `vitest.config.ts` during Wave 0 |
| **Quick run command** | `cd cloud/server && npm test` |
| **Full suite command** | `cd cloud/server && npm test` (+ `cd cloud/platform && npx playwright test` for UI) |
| **Estimated runtime** | ~30–60 seconds (server) |

---

## Sampling Rate

- **After every task commit:** Run `cd cloud/server && npm test`
- **After every plan wave:** Run the full server suite (+ Playwright for UI waves)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Seeded from RESEARCH.md "Validation Architecture" + phase Success Criteria. The planner refines task IDs/commands per plan.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| migration-applies | schema | 1 | REQ-knowledge-connectors | — | Integration/Issue tables + Project.linearTeamId exist after push | integration | `cd cloud/server && npx prisma db push --force-reset && npm test` | ❌ W0 | ⬜ pending |
| github-sync-upsert | github | 2 | REQ-orch-issue-intake | T-20-01 (token leak) | repo issues upsert into Issue; OrgMember-gated | integration | `npm test -- issues-github` | ❌ W0 | ⬜ pending |
| github-pr-exclusion | github | 2 | REQ-orch-issue-intake | — | items with `pull_request` key are NOT ingested | unit | `npm test -- pr-exclusion` | ❌ W0 | ⬜ pending |
| sync-idempotent | github | 2 | REQ-orch-issue-intake | — | second sync → same row count, syncedAt advances | integration | `npm test -- idempotent` | ❌ W0 | ⬜ pending |
| linear-team-mapping | linear | 3 | REQ-knowledge-connectors | — | bound Team's issues map to the Project; externalKey=ENG-### | integration | `npm test -- linear-mapping` | ❌ W0 | ⬜ pending |
| oauth-state-roundtrip | linear | 3 | REQ-knowledge-connectors | T-20-02 (CSRF/state) | signed `state` JWT verified on callback; token stored | integration | `npm test -- oauth-state` | ❌ W0 | ⬜ pending |
| issues-list-route | api | 2 | REQ-orch-issue-intake | T-20-03 (cross-org read) | GET …/issues returns only that project's issues to a member | integration | `npm test -- issues-route` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `cloud/server/test/issues-github.test.ts` — GitHub sync + PR-exclusion + idempotency stubs (REQ-orch-issue-intake)
- [ ] `cloud/server/test/issues-linear.test.ts` — Linear Team→Project mapping + OAuth state stubs (REQ-knowledge-connectors)
- [ ] `cloud/server/test/issues-route.test.ts` — list-route RBAC stubs
- [ ] Confirm `vitest.config.ts` + the existing `db push --force-reset` test fixture; reuse, do not re-invent

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Linear OAuth full round-trip | REQ-knowledge-connectors | Needs a registered Linear OAuth app + live consent screen (env blocker, not in CI) | Register Linear app, set LINEAR_CLIENT_ID/SECRET/REDIRECT_URI, connect from platform, confirm token stored + team list returned. Gate as `checkpoint:human-verify`. |
| GitHub private-repo issue read (scope check A1) | REQ-orch-issue-intake | Depends on the Clerk GitHub connection's granted scopes | Sync a private repo; if 403, the Clerk OAuth config needs `repo` scope. |
| Issues UI render + "Sync now" | REQ-orch-issue-intake | Visual/interaction | Playwright walk via DEV-AUTH bypass: open a project, click Sync, assert issue rows + counts update. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags (use `vitest run`, never `vitest --watch` in CI)
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
