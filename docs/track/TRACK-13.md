# TRACK-13 — Notifications

## Overview
The delivery layer for every event other surfaces generate: in-app + email + one-way Slack webhook, per-event-type settings, digest mode, per-repo/ticket mute, billing-event routing, and approval-escalation pings. Primary personas: IC (approval/review/stuck pings), EM (digest, mute), PLAT (Slack webhook), FIN (billing events), VPE (escalation). Purely a fan-out surface — it owns no events of its own; it routes the plan-gate (TRACK-4), CI-halt (TRACK-7), comment-loop-cap (TRACK-9), failure (TRACK-11), and billing (TRACK-12) events to channels.
Source: ORCHESTRATOR-USER-STORIES.md §13.

---

## User stories

13.1 **[IC]** Receive an in-app + email notification when (a) a plan needs my approval, (b) a PR is ready for my review, (c) a craw is stuck on a ticket I own. *AC: notification settings per-event-type; unsubscribe per type.*

13.2 **[EM]** Configure a digest mode: receive a daily summary instead of individual notifications. *AC: digest is per-user; orchestrator-wide events (e.g., budget cap hit) still send immediately.*

13.3 **[EM]** Mute notifications for a specific repo or ticket. *AC: mute lifts after a configurable window or manually.*

13.4 **[PLAT]** Configure a Slack webhook to receive workspace events (PRs opened, tasks failed, budget hit). *AC: Slack is one-way notification only in v1; no inbound chat to the bot.*

13.5 **[FIN]** Receive a billing-event notification (overage, cap hit, invoice paid) directly. *AC: routes to billing email, not to general user notification stream.*

13.6 **[VPE]** Configure escalation: if a plan-approval notification goes unanswered for 24h, ping a fallback reviewer. *AC: fallback chain configurable per workspace.*

13.7 **[deferred → v2]** Discord, Microsoft Teams, PagerDuty integrations.

---

## Coding tasks (from ROADMAP.md)

- **O6.4** — Notifications (in-app + email + one-way Slack webhook) (`cloud/server/src/notifications/`) — implements §13.1 (in-app + email, per-event-type settings, unsubscribe), §13.2 (digest mode, per-user, immediate override for org-wide events), §13.3 (per-repo/ticket mute with window), §13.4 (one-way Slack webhook), §13.5 (billing-event routing to billing email).

Note: §13.6 escalation (24h-unanswered → fallback reviewer) is implemented by **O6.2** (Escalation policy + UI, TRACK-4/TRACK-11), with O6.4 as the delivery channel. The fallback chain lives in O6.2; O6.4 sends the ping. Cross-reference TRACK-4 §4.7 (same SLA/escalation machinery).

Note: §13.7 Discord / Teams / PagerDuty is `[deferred → v2]`. ROADMAP confirms ("PagerDuty/Discord/Teams remain deferred"). No O-stage; correctly carries no code.

---

## Tech stack considerations

- §13.4 Slack is explicitly one-way in v1 (no inbound chat to the bot) — this keeps the bot's interaction surface to GitHub/Linear comments (TRACK-9) and avoids a second command channel. Don't build Slack event ingestion; it's a webhook POST sink only. SMTP for email was pulled forward from GRAND_PLAN Stage 2 to here (ROADMAP §"out of scope" note).
- §13.2 digest mode is per-user but org-wide events (budget cap hit) bypass digest and send immediately — the router needs an event-severity flag distinguishing "digestible" from "must-deliver-now," not just an event type. This severity flag is the same signal §13.5 uses to route billing events out of the general stream.
- §13.5 billing events route to the billing email, not the general user notification stream — a separate destination from §13.1's per-user channels. The notification system has at least two address books (user notification prefs vs. org billing contact); keep them distinct so a FIN persona without a user seat still receives cap-hit emails.
- §13.1 per-event-type settings with per-type unsubscribe means notification preferences are a matrix (user × event-type × channel), not a single on/off. The three v1 event triggers (plan-approval, PR-ready, stuck-on-my-ticket) each need an ownership resolver ("a ticket I own") that reads assignment from Linear/GitHub.
- §13.3 mute with a configurable lift window is a temporary suppression with an expiry — needs a scheduled lift, which reuses the durable-timer mechanism behind the §4.7 SLA timer. Don't build a second timer system.
- §13.6 escalation depends on O6.2's fallback chain and the durable 24h timer; the notification layer only delivers. Open question: does the 24h SLA run wall-clock or business-hours? Same unresolved question as TRACK-4 §4.7 — answer once, apply to both.
