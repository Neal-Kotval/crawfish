# TRACK-12 — Billing & seats

**Components:** `PLAT` (all of it)
**Source:** ORCHESTRATOR-USER-STORIES.md §12 · ROADMAP O-stages O5.1, O5.4, O5.5, O5.6 · consumes PARALLEL TRACK D (weeks 14–16)

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the monetization surface, and it lives entirely on `PLAT` because billing state must be
canonical (ADR-003: cloud Postgres is the source of truth). It covers Stripe subscription
(card or invoice), per-human-seat pricing, a per-seat usage allowance with metering above it,
seat-overage warnings, a hard monthly budget cap that pauses dispatch, a projected end-of-month
cost, seat add/remove with proration, and PDF invoices.

The defining convention — from GRAND_PLAN §3.2's Linear convention — is **humans are billable
seats, agents never count**. This is the core billing invariant, and it must be enforced where
seats are *counted* (the Prisma query), not in the UI. If the seat count is computed in a React
component, an agent `OrgMember` could slip into the total and inflate the bill; enforce it at the
data layer so there is exactly one place the rule lives.

This track *consumes* the Stripe + team-mode + audit work originally scoped as PARALLEL TRACK D
(weeks 14–16); it is sequenced here as the O5 stages. There is one cross-track inconsistency to
resolve: §12.5's cost forecast is v1, but the same forecast appears in TRACK-10 §10.8 as v1.5.
That tier conflict is flagged below.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Subscribe card/invoice (§12.1) | `PLAT` | `cloud/server/src/billing/{stripe,seats,usage}.ts` (O5.1) |
| Seat usage + overage warnings (§12.2) | `PLAT` | seat enforcement, shared with O5.1 (O5.4) |
| Per-seat usage allowance + metering (§12.3) | `PLAT` | usage metering, shared with O5.1 (O5.5) |
| Hard monthly budget cap + pause (§12.4) | `PLAT` | `cloud/server/src/billing/budget-cap.ts` (O5.6) |
| Projected end-of-month cost (§12.5) | `PLAT` | **unmapped — see Gaps; tier conflict with §10.8** |
| Add/remove seats + proration (§12.6) | `PLAT` | Stripe-native, in O5.1 |
| PDF invoices + email (§12.7) | `PLAT` | Stripe-native, in O5.1 |
| Per-team budget envelopes (§12.8) | `PLAT` | `[v1.5]` — correctly deferred |

---

## User stories

Tags are now **components** (where it gets built), not personas.

12.1 **[PLAT]** Subscribe with a credit card or invoice; per-seat for humans (agents are free per GRAND_PLAN §3.2 Linear convention). *AC: Stripe Connect on `cloud/server`; seat pricing displayed at signup; usage metering disclosed.*

12.2 **[PLAT]** See current seat usage vs. plan, with overage warnings before they hit the bill. *AC: warning at 80% and 100% of seats.*

12.3 **[PLAT]** Configure the usage allowance per seat (e.g., 100k tokens per seat per month); above this, usage is metered at a per-token rate. *AC: clear rate disclosure; rolls over no; resets monthly.*

12.4 **[PLAT]** Set a hard monthly budget cap; when hit, the orchestrator stops dispatching new tasks and emails the admin. *AC: in-flight tasks complete; new tasks queue with "paused for budget" status.*

12.5 **[PLAT]** See projected end-of-month cost based on the first N days' burn. *AC: linear projection; updates daily.*

12.6 **[PLAT]** Add or remove human seats from the org; pro-rate the change on the next invoice. *AC: standard Stripe behavior; no surprise.*

12.7 **[PLAT]** Download invoices as PDF; receive each invoice as an email attachment. *AC: invoices comply with standard formats; tax info supported per Stripe.*

12.8 **[v1.5]** **[PLAT]** Per-team budget envelopes within the same workspace.

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O5.1** — Stripe Connect integration, humans bill / agents don't (`cloud/server/src/billing/{stripe,seats,usage}.ts`). Implements §12.1 subscribe (card/invoice), §12.6 seat add/remove with proration, and §12.7 PDF invoices + tax. Lean on Stripe's invoice and proration engine — "standard Stripe behavior, no surprise" (§12.6) means do not reimplement billing math. The custom work is the per-seat allowance and token metering (O5.5), not the dunning or proration logic.

  ```ts
  // cloud/server/src/billing/seats.ts — the billing invariant lives HERE, at the data layer.
  // Only humanity=human members count as seats; agents are free (GRAND_PLAN §3.2).
  export async function billableSeatCount(orgId: string) {
    return db.orgMember.count({
      where: { orgId, humanity: "human" }, // agents excluded at the query, not in the UI
    });
  }
  ```

- **O5.4** — Seat enforcement (shared with O5.1). Implements §12.2: current seat usage vs. plan, with warnings at 80% and 100%. These are **seat-count** thresholds — distinct from the token budget cap (§12.4). Two warning systems exist (seats vs. spend); they must not be conflated when notifications route them (TRACK-13 §13.5 sends billing events to the billing email, not the general stream).

- **O5.5** — Usage metering above per-seat allowance (shared with O5.1). Implements §12.3: a per-seat allowance (e.g. 100k tokens/seat/month), metered at a per-token rate above it, resets monthly, no rollover. This requires a **metered token ledger** that attributes spend to seats and resets on a monthly boundary. The same ledger feeds analytics (TRACK-10) and must reconcile with the CSV export (§10.6) — one ledger, not two.

  ```ts
  // O5.5 — wire the token ledger to Stripe metered billing on the monthly boundary.
  const used = await ledger.tokensThisPeriod(orgId);          // from the one ledger
  const allowance = seats * ALLOWANCE_PER_SEAT;               // e.g. 100_000 * seats
  const metered = Math.max(0, used - allowance);              // no rollover; resets monthly
  if (metered > 0) {
    await stripe.subscriptionItems.createUsageRecord(meteredItemId, {
      quantity: metered, timestamp: periodEnd, action: "set",
    });
  }
  ```

- **O5.6** — Monthly budget cap + pause (`cloud/server/src/billing/budget-cap.ts`). Implements §12.4: a hard cap that, when hit, stops dispatching new tasks (in-flight tasks complete), queues new tasks with a "paused for budget" status, and emails the admin. This shares the **pause-and-queue mechanic** with the per-task / per-org caps (TRACK-5 §5.6, O1.6) — all three read `budget.ts`. It is the same reversible workflow state as the per-task pause; do not build a second pause path.

  ```ts
  // budget-cap.ts — same reversible state as TRACK-5 §5.6, different trigger (monthly spend).
  if (monthlySpend >= org.monthlyCapCents) {
    await db.org.update({ where: { id: orgId }, data: { dispatchState: "paused-budget" } });
    await notify.admin(orgId, "monthly budget cap hit; new tasks paused");
    // Dispatcher checks dispatchState before sending; in-flight tasks are untouched.
    // Lifting the cap (or new month) flips state back to "active". Reversible.
  }
  ```

**Reuses (already shipped):**
- `OrgMember` Prisma model (PLAT) — the seat substrate. A member row carries `humanity`; per GRAND_PLAN §3.2 only `humanity = "human"` members count toward seats.

**Consumes:** PARALLEL TRACK D weeks 14–16 — the same Stripe + seat + audit work, sequenced here as O5 (ROADMAP §"Consumes PARALLEL TRACK D").

Cross-refs: O5.6 pause shares state with TRACK-5 §5.6 / O1.6. The O5.5 ledger feeds TRACK-10 analytics and reconciles with §10.6 CSV. Billing-event routing is TRACK-13 §13.5.

---

## Key technical concepts, explained

**Humanity = human seat gate at the Prisma layer (§12.1).** The billing invariant — agents are
free, humans are billable — is one line in a query, and it has to live exactly there. If a React
component sums seats, an agent `OrgMember` can leak into the count and inflate the bill, and the
bug is invisible until someone reads the invoice. Enforce it in `billableSeatCount()` (above):
`where: { humanity: "human" }`. Every other surface (signup pricing, the 80%/100% warnings, the
proration on add/remove) reads that one function. One gate, one place to audit.

**Stripe metered billing tied to the token ledger (§12.3, §12.5).** The per-seat allowance and
overage metering are *not* hand-rolled billing math. Stripe supports metered (usage-based)
subscription items: you report a usage quantity each period and Stripe bills it at the configured
rate. The work is wiring O5.5's token ledger to Stripe's `createUsageRecord` on the monthly
boundary (above), and making that *same* ledger the source for analytics (TRACK-10) and the CSV
export (§10.6). The danger is two ledgers disagreeing — one feeds the bill, one feeds the
dashboard, and the customer notices. There is one ledger.

**Monthly cap pause = the same reversible state as budget caps (§12.4).** "Stop dispatching when
the monthly cap is hit" is identical in shape to the per-task budget pause in TRACK-5 §5.6: flip
a `dispatchState` field, let in-flight work finish, queue new tasks as `paused-budget`, and flip
back when the cap lifts or the month rolls over. The only difference is the trigger (monthly spend
vs. per-task budget). Reuse the TRACK-5 pause path — a second, parallel pause implementation is a
divergence waiting to happen.

---

## Gaps — work with no O-stage assigned

These stories have acceptance criteria but **no numbered O0–O7 deliverable.** Flag for the lead.

- **§12.5 projected end-of-month cost — and a tier conflict with §10.8.** A linear projection from
  the first N days' burn, updated daily, has no numbered deliverable here. Worse, the *same* forecast
  appears in TRACK-10 §10.8 tagged `[v1.5]`, while §12.5 is **v1**. The two stories disagree on tier
  and both forecast monthly cost. *What's needed:* the lead reconciles whether these are one widget at
  one tier. The cheap answer: build the linear projection once at v1 (§12.5's tier) and treat §10.8's
  "accuracy improves over 30 days" as a later refinement, not a separate widget.

- **§12.8 per-team budget envelopes** is `[v1.5]` — no v1 O-stage, correctly deferred. Listed for
  completeness, not flagged as missing.

---

## Open questions

- **§12.5 vs §10.8 tier:** is the end-of-month cost forecast a v1 deliverable (§12.5) or a v1.5 one
  (§10.8)? They cannot both be authoritative. Resolve to one tier and one widget before either is
  built, or two teams ship two forecasts that drift.
- **§12.3 allowance reset boundary:** "resets monthly, no rollover" — does the monthly boundary follow
  the Stripe billing cycle or a fixed calendar month? The token ledger reset (O5.5) and the Stripe
  metered period must use the same boundary, or metered overage is computed against a window that
  doesn't match the invoice.
