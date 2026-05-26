# TRACK-12 — Billing & seats

## Overview
The monetization surface: Stripe Connect subscription, per-human-seat pricing (agents are free), usage metering above a per-seat allowance, seat-overage warnings, a hard monthly budget cap with pause, projected end-of-month cost, seat add/remove with proration, and PDF invoices. Primary personas: FIN (subscribe, allowance, cap, invoices), VPE (projection), EM (seat changes). Consumes the team-mode + Stripe work originally in PARALLEL TRACK D (weeks 14–16), sequenced here as O5. The defining convention: humans are billable seats, agents never count.
Source: ORCHESTRATOR-USER-STORIES.md §12.

---

## User stories

12.1 **[FIN]** Subscribe with a credit card or invoice; per-seat for humans (agents are free per GRAND_PLAN §3.2 Linear convention). *AC: Stripe Connect on `cloud/server`; seat pricing displayed at signup; usage metering disclosed.*

12.2 **[FIN]** See current seat usage vs. plan, with overage warnings before they hit the bill. *AC: warning at 80% and 100% of seats.*

12.3 **[FIN]** Configure the usage allowance per seat (e.g., 100k tokens per seat per month); above this, usage is metered at a per-token rate. *AC: clear rate disclosure; rolls over no; resets monthly.*

12.4 **[FIN]** Set a hard monthly budget cap; when hit, the orchestrator stops dispatching new tasks and emails the admin. *AC: in-flight tasks complete; new tasks queue with "paused for budget" status.*

12.5 **[VPE]** See projected end-of-month cost based on the first N days' burn. *AC: linear projection; updates daily.*

12.6 **[EM]** Add or remove human seats from the org; pro-rate the change on the next invoice. *AC: standard Stripe behavior; no surprise.*

12.7 **[FIN]** Download invoices as PDF; receive each invoice as an email attachment. *AC: invoices comply with standard formats; tax info supported per Stripe.*

12.8 **[v1.5]** **[FIN]** Per-team budget envelopes within the same workspace.

---

## Coding tasks (from ROADMAP.md)

- **O5.1** — Stripe Connect integration (humans bill, agents don't) (`cloud/server/src/billing/{stripe,seats,usage}.ts`) — implements §12.1 subscribe (card/invoice), §12.6 seat add/remove proration, §12.7 PDF invoices + tax.
- **O5.4** — Seat enforcement (shared with O5.1) — implements §12.2 seat usage vs. plan + 80%/100% overage warnings.
- **O5.5** — Usage metering above per-seat allowance (shared with O5.1) — implements §12.3 (per-seat allowance, per-token metering above, monthly reset, no rollover).
- **O5.6** — Monthly budget cap + pause (`cloud/server/src/billing/budget-cap.ts`) — implements §12.4 (hard cap → stop dispatch, in-flight completes, "paused for budget" queue status, email admin).
  - Reuses: existing `OrgMember` Prisma model — the seat substrate; per GRAND_PLAN §3.2 Linear convention only humanity=human members count.
  - Consumes: **PARALLEL TRACK D weeks 14–16** — same Stripe + seat + audit work, sequenced as O5 (ROADMAP §"Consumes PARALLEL TRACK D").

Gap / flag: §12.5 **projected end-of-month cost** (linear projection from first N days, daily update) has no numbered deliverable — it overlaps TRACK-10 §10.8 `[v1.5]` bill forecast but §12.5 is *not* tagged v1.5. Inconsistency: §12.5 is v1-scoped, §10.8 is v1.5, and both forecast monthly cost. Lead should reconcile whether these are one widget at one tier.

Note: §12.8 per-team budget envelopes is `[v1.5]` — no v1 O-stage; correctly deferred.

---

## Tech stack considerations

- Stripe Connect on `cloud/server`; seat enforcement at the Prisma `OrgMember` layer with a humanity=human gate — agents never count toward seats (§12.1, GRAND_PLAN §3.2). This gate is the core billing invariant; it must be enforced in the seat query, not the UI, or an agent member could inflate the seat count.
- §12.4 monthly budget cap (O5.6) shares the pause-and-queue mechanic with the per-task / per-org caps (TRACK-5 §5.6, O1.6) — all three read `budget.ts`. "In-flight completes, new tasks queue as paused-for-budget" is the same reversible workflow state as the per-task pause; don't build a second pause path.
- §12.3 usage allowance (default-style 100k tokens/seat/month, metered above, resets monthly, no rollover) requires the metered token ledger (O5.5) to attribute spend to seats and reset on a monthly boundary; the same ledger feeds analytics (TRACK-10) and must reconcile with the CSV export (§10.6). One ledger.
- §12.5 / §10.8 forecast: a linear projection from N days' burn is cheap, but the two stories disagree on tier (v1 vs v1.5). If built once, build at v1 (§12.5's tier) and let §10.8's "accuracy improves over 30 days" be a refinement, not a separate widget.
- §12.7 invoices are Stripe-native (PDF, tax, email attachment) — "standard Stripe behavior, no surprise" (§12.6) means lean on Stripe's invoice + proration engine rather than reimplementing billing math. The custom work is the per-seat allowance + token metering (O5.5), which Stripe metered billing supports but must be wired to the token ledger.
- §12.2 warnings at 80%/100% of seats are seat-count thresholds (O5.4), distinct from the token budget cap (§12.4); two warning systems (seats vs. spend) that must not be conflated in the notification routing (TRACK-13 §13.5 routes billing events to the billing email, not the general stream).
