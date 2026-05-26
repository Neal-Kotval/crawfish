# TRACK-1 — Onboarding & account setup

## Overview
The entry surface for a new customer: GitHub-OAuth signup, workspace creation, teammate invites, and the integration connects (Linear, GitHub, CI) that make a workspace craw-eligible. It ends in a guided empty-state walkthrough that produces a real merged PR. Primary personas: VPE (buyer, signs up), EM (invites, day-to-day admin), PLAT (wires Linear / GitHub / CI). Sits at the very front of the orchestrator lifecycle — nothing else in the product runs until a workspace exists and at least one repo is connected.
Source: ORCHESTRATOR-USER-STORIES.md §1.

---

## User stories

1.1 **[VPE]** Sign up via GitHub OAuth and create a workspace in under 90 seconds. *AC: GitHub OAuth, workspace name, billing email → land in the empty dashboard with a "connect your first repo" CTA.*

1.2 **[EM]** Invite teammates by email or by domain auto-match, with a role chosen at invite time (admin, member, viewer). *AC: invitee receives email with magic-link accept; on accept they land in the workspace; OrgMember.role persisted (existing Prisma model).*

1.3 **[PLAT]** Connect Linear via OAuth and select which teams / projects are eligible. *AC: per-team toggle; webhook subscriptions registered; selection persisted.*

1.4 **[PLAT]** Connect GitHub via the existing GitHub App OAuth (already in `cloud/server`); select which repos are eligible for craw activity. *AC: per-repo toggle; PR-write scope confirmed; repos with PR-write disabled appear read-only.*

1.5 **[PLAT]** Connect the CI provider (GitHub Actions detected automatically from connected repos; CircleCI / GitLab CI as v1.5). *AC: orchestrator can read CI status on a PR via the provider's API; failures fetch logs.*

1.6 **[VPE]** Land in a 4-step empty-state walkthrough that ends with a real "boring & bounded" PR opened against a sandbox repo within 10 minutes. *AC: walkthrough uses the customer's own GitHub account; sandbox repo is forked from a Crawfish-provided template; PR is real and merges with one click.*

1.7 **[EM]** Convert a personal workspace to a team workspace and re-route billing to the team admin. *AC: irreversible action; confirms migration of existing PRs to team ownership.*

1.8 **[deferred → v2]** SSO / SAML / OIDC.

---

## Coding tasks (from ROADMAP.md)

- **O0.2** — Cloud-server orchestrator skeleton (`cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts`) — the server surface a workspace's first run depends on.
- **O1.1** — Linear webhook receiver (`cloud/server/src/inbound/linear.ts`) — implements §1.3 connect-Linear (webhook subscriptions registered on team selection).
- **O1.2** — GitHub Issues poller (`cloud/server/src/inbound/github-issues-poller.ts`) — fallback ingestion for connected GitHub repos.
- **O2.7** — Per-craw routing rules UI (`cloud/platform/src/pages/RoutingRules.tsx`) — configured during onboarding once repos are eligible.
- **O6.1** — Onboarding walkthrough (ends with real PR in <10min) (`cloud/platform/src/onboarding/orchestrator/`) — implements §1.6 directly.
  - Reuses: existing Clerk auth + GitHub App OAuth already shipped in `cloud/server` (§1.1, §1.4 per USER-STORIES §17).
  - Reuses: existing `OrgMember` Prisma model for §1.2 role persistence.

Gap: §1.4's **per-repo PR-write eligibility toggle** has no dedicated O-stage deliverable. USER-STORIES §17 names it explicitly as a gap ("per-repo PR-write toggle, CI provider linking"). It is implied work under O1.x but unnumbered — lead should assign it.

Gap: §1.5's **CI-provider connect/config UI** is not a numbered deliverable. O1.7 (CI gate) reads GitHub Actions status but does not include a connect screen; CircleCI / GitLab is `[v1.5]`. Flagging the connect surface as unassigned.

Gap: §1.7 **personal → team workspace conversion + billing re-route** maps to no O-stage. Billing lives in O5.1 but the irreversible workspace-conversion flow is not called out. Flag for assignment.

Note: §1.2's email/domain invite overlaps **O5.7 invite flow polish**, which the canonical map assigns to TRACK-16. Onboarding consumes that work; it is not duplicated here.

Note: §1.8 SSO/SAML/OIDC is `[deferred → v2]` and is Stage-3 per ROADMAP "Explicitly out of scope". No O-stage; correctly carries no code.

---

## Tech stack considerations

- Clerk + GitHub App OAuth already ship in `cloud/server`; §1.1 and §1.4 are wiring, not greenfield auth. The new surface is the workspace-creation flow and the per-repo eligibility toggle, not the identity layer.
- §1.6's "real PR in <10 min" requires a Crawfish-provided template repo the customer forks under their own GitHub account. The walkthrough must drive a live `O0.4` dep-bumper run end-to-end, so onboarding is gated on the O0 spike being real, not mocked.
- §1.2 role persistence reuses the `OrgMember` Prisma model; humanity=human gating (see TRACK-12) means invited members are seats, not agents. Invite role must be set at invite time, not post-accept, to avoid an unscoped-access window.
- §1.7 is flagged irreversible and migrates existing PR ownership; this is a data-migration concern, not just a UI toggle. Open question: whether PR ownership is a foreign key re-point or a copy — affects audit-log continuity (TRACK-14).
- CI-provider connect (§1.5) reads status via provider API; GitHub Actions is auto-detected from connected repos, so the only v1 connect work is token scope confirmation. CircleCI/GitLab is deferred to v1.5 and should not shape the v1 data model beyond a provider enum.
