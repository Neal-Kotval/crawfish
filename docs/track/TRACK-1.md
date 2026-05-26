# TRACK-1 — Onboarding & account setup

**Components:** `PLAT` (primary) · `CLI` (the craw the walkthrough runs)
**Source:** ORCHESTRATOR-USER-STORIES.md §1 · ROADMAP.md O-stages O0.2, O1.1, O1.2, O2.7, O6.1

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the front door. A buyer signs up with GitHub, names a workspace, and connects the
three external systems the orchestrator needs to do anything: the **issue tracker** (Linear
or GitHub Issues — where work comes *in*), the **code host** (GitHub — where PRs go *out*),
and **CI** (GitHub Actions — what verifies a PR before a human sees it). It ends with a guided
walkthrough that produces one real, merged PR so the customer sees the loop close before they
trust it with real tickets.

Nothing else in the product runs until this is done: no workspace → no repos → no tickets to
classify → no tasks to execute. In the request lifecycle this is step 0.

The good news, from USER-STORIES §17: **Clerk auth and the GitHub App OAuth already ship in
`cloud/server`.** You are not building login. You are building workspace creation, the
per-repo eligibility toggle, and the connect flows on top of an identity layer that exists.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Sign up + create workspace (§1.1) | `PLAT` | `cloud/server` (workspace model) + `cloud/platform` (signup UI) |
| Invite teammates (§1.2) | `PLAT` | reuses `OrgMember` Prisma model |
| Connect Linear (§1.3) | `PLAT` | `cloud/server/src/inbound/linear.ts` (O1.1) |
| Connect GitHub repos (§1.4) | `PLAT` | reuses GitHub App OAuth; per-repo toggle is new |
| Connect CI (§1.5) | `PLAT` | `cloud/server/src/orchestrator/ci.ts` (O1.7) reads status |
| Empty-state walkthrough (§1.6) | `PLAT` + `CLI` | `cloud/platform/src/onboarding/orchestrator/` (O6.1) drives a `CLI` craw (O0.4) |
| Personal → team workspace (§1.7) | `PLAT` | **unmapped — see Gaps** |

---

## User stories

Tags are now **components** (where it gets built), not personas.

1.1 **[PLAT]** Sign up via GitHub OAuth and create a workspace in under 90 seconds. *AC: GitHub OAuth, workspace name, billing email → land in the empty dashboard with a "connect your first repo" CTA.*

1.2 **[PLAT]** Invite teammates by email or by domain auto-match, with a role chosen at invite time (admin, member, viewer). *AC: invitee receives email with magic-link accept; on accept they land in the workspace; OrgMember.role persisted (existing Prisma model).*

1.3 **[PLAT]** Connect Linear via OAuth and select which teams / projects are eligible. *AC: per-team toggle; webhook subscriptions registered; selection persisted.*

1.4 **[PLAT]** Connect GitHub via the existing GitHub App OAuth (already in `cloud/server`); select which repos are eligible for craw activity. *AC: per-repo toggle; PR-write scope confirmed; repos with PR-write disabled appear read-only.*

1.5 **[PLAT]** Connect the CI provider (GitHub Actions detected automatically from connected repos; CircleCI / GitLab CI as v1.5). *AC: orchestrator can read CI status on a PR via the provider's API; failures fetch logs.*

1.6 **[PLAT, CLI]** Land in a 4-step empty-state walkthrough that ends with a real "boring & bounded" PR opened against a sandbox repo within 10 minutes. *AC: walkthrough uses the customer's own GitHub account; sandbox repo is forked from a Crawfish-provided template; PR is real and merges with one click.*

1.7 **[PLAT]** Convert a personal workspace to a team workspace and re-route billing to the team admin. *AC: irreversible action; confirms migration of existing PRs to team ownership.*

1.8 **[deferred → v2]** SSO / SAML / OIDC.

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O0.2** — Cloud-server orchestrator skeleton (`cloud/server/src/orchestrator/{queue,worker,workflow,types}.ts`). The server scaffolding everything else attaches to: a queue tasks land in, a worker that drains it, a workflow definition, shared types. Onboarding needs this to exist so "connect a repo" has somewhere to register.

- **O1.1** — Linear webhook receiver (`cloud/server/src/inbound/linear.ts`). Implements §1.3. When the customer toggles a Linear team "eligible," you call Linear's API to **register a webhook subscription** so Linear pushes ticket events to you instead of you polling. Concretely:

  ```ts
  // cloud/server/src/inbound/linear.ts — on team-eligible toggle
  await linear.webhooks.create({
    teamId,
    url: `${PUBLIC_URL}/inbound/linear`,   // Linear POSTs here on every ticket event
    resourceTypes: ["Issue", "Comment"],
    secret: webhookSigningSecret,          // used to verify the payload is really Linear
  });
  // Persist the subscription id so "untoggle" can delete it and you don't leak webhooks.
  await db.linearWebhook.create({ data: { teamId, webhookId: created.id } });
  ```

  The webhook handler must **verify the signature** (HMAC of the body with `secret`) before
  trusting the payload — otherwise anyone who learns your URL can inject fake tickets.

- **O1.2** — GitHub Issues poller (`cloud/server/src/inbound/github-issues-poller.ts`). The fallback for repos where you can't register a webhook: poll the Issues API on a schedule. (Detailed in TRACK-3, where ingestion is the focus.)

- **O2.7** — Per-craw routing rules UI (`cloud/platform/src/pages/RoutingRules.tsx`). Configured during onboarding once repos are eligible: "label `dep-bump` → dep-bumper craw." (Detailed in TRACK-2.)

- **O6.1** — Onboarding walkthrough (`cloud/platform/src/onboarding/orchestrator/`). Implements §1.6 — the 4-step flow that ends in a real PR. This is a UI sequence that drives the *real* execution path end-to-end (not a mock), so it is gated on O0.4 (a working craw) and O1.x (the PR loop) actually running.

**Reuses (already shipped — do not rebuild):**
- Clerk auth + GitHub App OAuth in `cloud/server` (covers §1.1 login and §1.4 GitHub connect).
- `OrgMember` Prisma model for §1.2 role persistence. A member row already carries a `role`; invites set it at invite time.

### CLI — `cli/orgctl`

- **O0.4** — First curated craw, the dep-bumper (`cli/orgctl/src/craws/dep-bumper/{craw.yaml,SKILL.md,impl.ts}`). The walkthrough (§1.6) runs *this* craw against the sandbox repo to produce the demo PR. It is "boring & bounded" on purpose: bumping a dependency is mechanical, low-risk, and visibly useful — the right first impression. (Owned by TRACK-2; listed here because onboarding depends on it.)

---

## Key technical concepts, explained

**GitHub App vs. GitHub OAuth (§1.4).** Two different things that both say "GitHub login."
*OAuth* identifies the human (who signed up). A *GitHub App* is an installable bot identity
with its own permissions and per-repo install — it's what lets the orchestrator open PRs as
`@crawfish-bot` rather than as the user. §1.4's "per-repo toggle" is really "which repos is
the App installed on, and is PR-write enabled there." Both already ship; the new work is the
toggle UI and persisting the eligibility flag.

**Idempotent workspace creation (§1.1, AC "under 90 seconds").** If the user double-clicks
"create" or the request retries, you must not create two workspaces. Key the create on
something stable:

```ts
// Safe: a second identical call returns the same row instead of making a new one.
await db.workspace.upsert({
  where: { ownerUserId_name: { ownerUserId, name } },
  create: { ownerUserId, name, billingEmail },
  update: {},   // already exists → no-op
});
```

**Webhook vs. poller (§1.3 vs §1.5/§3.6).** A webhook is push (the tracker calls you the
instant something happens — low latency, but needs a public URL and a registered subscription).
A poller is pull (you ask "anything new?" every N minutes — simpler, higher latency, must
dedup). Linear gets a webhook (§1.3); GitHub Issues falls back to polling where webhooks aren't
available (§3.6).

---

## Gaps — work with no O-stage assigned

These stories have acceptance criteria but **no numbered O0–O7 deliverable.** Flag for the lead.

- **§1.4 per-repo PR-write toggle.** USER-STORIES §17 names this explicitly as a gap. The GitHub App is installed, but "this repo is read-only vs. craw-writable" is a per-repo flag with no deliverable. *What's needed:* a `repoEligibility` field + a guard the PR step (TRACK-8) checks before opening a PR.
- **§1.5 CI-provider connect/config UI.** O1.7 (TRACK-7) *reads* CI status, but there is no screen to connect/confirm the provider. GitHub Actions is auto-detected, so v1 work is small (token-scope confirmation); CircleCI/GitLab is `[v1.5]`.
- **§1.7 personal → team conversion + billing re-route.** No O-stage. This is a data migration (re-point PR ownership, move the Stripe customer), not just a toggle — non-trivial and unowned.

---

## Open questions

- **§1.7 PR ownership migration:** is it a foreign-key re-point or a copy? This decides whether the audit-log history (TRACK-14) stays continuous across the conversion.
- **§1.2 vs O5.7:** invite *polish* is assigned to O5.7 (TRACK-16), but basic invite is needed at onboarding. Confirm whether onboarding ships a minimal invite and O5.7 polishes it, or onboarding waits for O5.7.
