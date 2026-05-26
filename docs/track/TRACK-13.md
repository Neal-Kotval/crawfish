# TRACK-13 — Notifications

**Components:** `PLAT` (the delivery layer) · `DASH` (the escalation-chain UI shared with O6.2)
**Source:** ORCHESTRATOR-USER-STORIES.md §13 · ROADMAP O-stages O6.4 (delivery), O6.2 (escalation chain)

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the fan-out layer. It owns **no events of its own** — it routes events other surfaces
generate to channels: the plan-gate (TRACK-4), the CI-halt (TRACK-7), the comment-loop cap
(TRACK-9), the failure record (TRACK-11), and billing events (TRACK-12). Its job is delivery:
in-app, email, and a one-way Slack webhook, with per-event-type settings, a digest mode, per-repo
or per-ticket mute, billing-event routing, and approval-escalation pings.

Two design decisions shape the whole surface. First, **digestible vs. must-deliver-now**: a digest
batches routine pings into a daily summary, but org-wide events (a budget cap hit) must bypass the
digest and send immediately. That means the router needs a *severity flag* on each event, not just
an event type. Second, **two address books**: per-user notification preferences are a different
destination from the org billing contact. A FIN persona who has no user seat still has to receive a
cap-hit email, so billing events route to the billing contact, not the general user stream.

The escalation ping (§13.6) is a split: the *fallback chain* lives in O6.2 (shared with TRACK-4
§4.7 and TRACK-11), and this surface (O6.4) only *delivers* the ping. Discord, Teams, and PagerDuty
are explicitly `[deferred → v2]` and carry no code.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| In-app + email per-event-type (§13.1) | `PLAT` | `cloud/server/src/notifications/` (O6.4) |
| Digest mode (§13.2) | `PLAT` | `cloud/server/src/notifications/` (O6.4) |
| Per-repo / ticket mute (§13.3) | `PLAT` | `cloud/server/src/notifications/` (O6.4) |
| One-way Slack webhook (§13.4) | `PLAT` | `cloud/server/src/notifications/` (O6.4) |
| Billing-event routing (§13.5) | `PLAT` | `cloud/server/src/notifications/` (O6.4) |
| Escalation chain config + ping (§13.6) | `PLAT` + `DASH` | chain in O6.2; ping delivered by O6.4 |
| Discord / Teams / PagerDuty (§13.7) | — | `[deferred → v2]` — no code |

---

## User stories

Tags are now **components** (where it gets built), not personas.

13.1 **[PLAT]** Receive an in-app + email notification when (a) a plan needs my approval, (b) a PR is ready for my review, (c) a craw is stuck on a ticket I own. *AC: notification settings per-event-type; unsubscribe per type.*

13.2 **[PLAT]** Configure a digest mode: receive a daily summary instead of individual notifications. *AC: digest is per-user; orchestrator-wide events (e.g., budget cap hit) still send immediately.*

13.3 **[PLAT]** Mute notifications for a specific repo or ticket. *AC: mute lifts after a configurable window or manually.*

13.4 **[PLAT]** Configure a Slack webhook to receive workspace events (PRs opened, tasks failed, budget hit). *AC: Slack is one-way notification only in v1; no inbound chat to the bot.*

13.5 **[PLAT]** Receive a billing-event notification (overage, cap hit, invoice paid) directly. *AC: routes to billing email, not to general user notification stream.*

13.6 **[PLAT, DASH]** Configure escalation: if a plan-approval notification goes unanswered for 24h, ping a fallback reviewer. *AC: fallback chain configurable per workspace.*

13.7 **[deferred → v2]** Discord, Microsoft Teams, PagerDuty integrations.

---

## Coding tasks, by component

### PLAT — `cloud/server`

- **O6.4** — Notifications: in-app + email + one-way Slack webhook (`cloud/server/src/notifications/`). The whole delivery layer. Implements §13.1 (in-app + email, per-event-type settings, per-type unsubscribe), §13.2 (digest mode, per-user, immediate override for org-wide events), §13.3 (per-repo/ticket mute with a lift window), §13.4 (one-way Slack webhook), and §13.5 (billing-event routing to the billing email).

  §13.1's per-event-type settings with per-type unsubscribe means preferences are a **matrix** (user × event-type × channel), not a single on/off:

  ```ts
  // notifications/prefs.ts — preference is a matrix, not a boolean.
  type Channel = "in_app" | "email" | "slack";
  type EventType = "plan_approval" | "pr_ready" | "stuck_on_my_ticket" | "billing" | ...;
  interface NotificationPref { userId: string; eventType: EventType; channel: Channel; enabled: boolean; }
  ```

  The digest router decides batch vs. immediate from a **severity flag**, not the event type:

  ```ts
  // notifications/route.ts — digestible events batch; must-deliver-now bypass the digest.
  if (event.severity === "must_deliver_now") {
    return deliver(event);                 // e.g. budget cap hit — sends even if user is on digest
  }
  if (user.digestMode) return enqueueDigest(event); // routine ping — batched into daily summary
  return deliver(event);
  ```

  The Slack webhook (§13.4) is a **one-way POST sink** — there is no inbound chat to the bot in v1:

  ```ts
  // notifications/slack.ts — fire-and-forget POST. No event ingestion, no bot commands.
  await fetch(workspace.slackWebhookUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text: renderSlackMessage(event) }),
  });
  ```

  Billing events (§13.5) route to a **separate address book** — the org billing contact, not the
  per-user stream — so a FIN with no user seat still gets a cap-hit email.

**Reuses (already shipped):**
- The durable-timer mechanism behind the §4.7 SLA timer (PLAT) — §13.3's mute-with-lift-window is a temporary suppression with an expiry; it schedules its lift on that same timer. Do not build a second timer system.
- JSONL audit + `OrgMember` (PLAT) — the audit trail records what was delivered; `OrgMember` carries the user notification preferences.

### DASH — `desktop/dash`

- **O6.2 escalation chain (UI half)** — §13.6's fallback chain is configured per workspace through the escalation-policy UI shipped in O6.2 (shared with TRACK-4 and TRACK-11). The dashboard owns the configuration screen; O6.4 owns the actual ping. The chain answers "who is the fallback after 24h"; the notification layer only delivers to whoever the chain names.

**Notes on scope:**
- §13.6 escalation is implemented by **O6.2** (escalation policy + UI, TRACK-4 / TRACK-11), with O6.4 as the delivery channel. The fallback chain lives in O6.2; O6.4 sends the ping. Same SLA/escalation machinery as TRACK-4 §4.7 — answer the SLA-clock question once, apply to both.
- §13.7 Discord / Teams / PagerDuty is `[deferred → v2]`. ROADMAP confirms ("PagerDuty/Discord/Teams remain deferred"). No O-stage; correctly carries no code.
- SMTP for email was pulled forward from GRAND_PLAN Stage 2 to here (ROADMAP §"out of scope" note); the email channel is in-scope for v1.

---

## Key technical concepts, explained

**Digestible vs. must-deliver-now severity flag (§13.2).** Digest mode batches routine pings into
a daily email, but an org-wide event — a budget cap hit — must bypass the digest and send the
instant it fires. If the router decides batch-vs-immediate from the *event type* it has to special-
case every new event. Instead, stamp each event with a `severity` (`digestible` |
`must_deliver_now`) and route on that one field (see `route.ts` above). This is the *same* signal
§13.5 uses to keep billing events out of the general stream — one flag, two routing decisions.

**Two address books (§13.5).** Per-user notification preferences and the org billing contact are
distinct destinations. The general stream (§13.1) delivers to the user who owns the ticket or
review; billing events (overage, cap hit, invoice paid) deliver to the org's billing contact. The
reason they must stay separate: a FIN persona may have no user seat at all, yet still has to
receive a cap-hit email. Two address books, looked up by different keys (user id vs. org billing
contact), so neither can starve the other.

**Slack one-way webhook POST sink (§13.4).** A Slack incoming webhook is a URL you POST JSON to;
Slack renders it as a message. That is the entire integration in v1 — fire-and-forget, no inbound.
Crucially there is **no event ingestion** and no bot command surface, which keeps the bot's
interactive surface confined to GitHub/Linear comments (TRACK-9) and avoids standing up a second
command channel. Build the POST sink (above); do not build a Slack event listener.

**Mute reuses the SLA durable timer (§13.3).** A mute with a configurable lift window is a temporary
suppression that must auto-expire — which needs a durable scheduled action that survives a restart.
That is exactly the durable-timer mechanism behind the §4.7 SLA timer. Schedule the mute lift on it
rather than standing up a second timer system that can drift out of sync.

---

## Gaps — work with no O-stage assigned

No story in §13 lacks an owner. Every v1 story is covered by O6.4 (delivery) or O6.2 (the §13.6
escalation chain), and §13.7 is correctly `[deferred → v2]` with no code. The one item to watch is
not a missing deliverable but an unresolved question shared with TRACK-4 — see below.

---

## Open questions

- **SLA wall-clock vs. business-hours (shared with TRACK-4 §4.7).** §13.6's "unanswered for 24h →
  ping the fallback" depends on O6.2's fallback chain and the durable 24h timer. Does that 24h run
  wall-clock or business-hours? This is the *same* unresolved question as TRACK-4 §4.7 — answer it
  once and apply to both, or the escalation timer and the SLA timer count differently against the
  same deadline.
