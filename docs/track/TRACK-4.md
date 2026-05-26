# TRACK-4 — Plan checkpoint (gate 1)

## Overview
The first human gate. Before any code is written, the craw posts its proposed plan to the ticket and waits for approval; humans approve, reject, or edit-and-re-approve, with optional auto-approval per label and a workspace-wide policy backstop. Primary personas: IC (approves/rejects/edits the plan), EM (configures auto-approval, SLA), VPE (sets workspace policy). Sits between classification (TRACK-3) and execution (TRACK-5) — nothing executes until this gate clears.
Source: ORCHESTRATOR-USER-STORIES.md §4.

---

## User stories

4.1 **[IC]** Before any code is written, the orchestrator posts the craw's proposed plan as a comment on the ticket and waits for human approval. *AC: plan is a markdown comment with: what files will change, which tests will run, expected diff size, estimated token cost; status changes to "awaiting plan approval."*

4.2 **[IC]** Approve the plan with a single emoji/reaction or a click in the dashboard. *AC: 👍 reaction in Linear or the "approve" button in the dashboard both work; logged with actor.*

4.3 **[IC]** Reject the plan with a one-line reason; the craw halts and the ticket returns to the backlog. *AC: rejection reason posted as a comment; ticket re-classifiable on next pass.*

4.4 **[IC]** Edit the plan inline (e.g., "also touch `src/billing.ts`") and re-approve. *AC: craw re-runs against the edited plan; original plan archived.*

4.5 **[EM]** Configure auto-approval for specific labels (e.g., `dep-bump` auto-approves the plan because the action is mechanical). *AC: auto-approval logs an "auto-approved" event; reviewer still has the merge gate.*

4.6 **[VPE]** Set a workspace-wide policy: "all plans require human approval" OR "plans auto-approve unless flagged risky." *AC: a craw can flag its own plan as risky (large diff, sensitive file path); risky always requires human review regardless of policy.*

4.7 **[EM]** Receive an in-app + email notification when a plan is awaiting my approval for more than the SLA window (default 4h). *AC: SLA configurable per workspace; escalation to backup reviewer after a second timeout.*

---

## Coding tasks (from ROADMAP.md)

- **O1.3** — Plan checkpoint workflow (gate 1) (`cloud/server/src/orchestrator/checkpoints/plan.ts`) — implements §4.1–§4.5: post plan, await approval, approve/reject/edit, per-label auto-approval, "awaiting plan approval" status.
- **O6.2** — Escalation policy + UI (fallback reviewer chain) (dashboard) — implements §4.6 workspace policy and §4.7 SLA escalation to a backup reviewer.

Note: §4.7 notification *delivery* (in-app + email) is **O6.4** (TRACK-13). O6.2 owns the escalation chain and SLA timer; O6.4 owns the channel. Both are required for §4.7; the canonical map lists only O1.3 + O6.2 for this surface — flagging that §4.7 depends on TRACK-13's O6.4.

Note: §4.4 "original plan archived" implies plan versioning in `plan.ts`; not separately numbered. The archived plan must be reachable from the audit log (TRACK-14) so an edited-then-approved plan has a trail.

---

## Tech stack considerations

- The plan checkpoint must survive a worker crash without re-firing the side-effect — re-posting the plan comment or re-prompting for approval on restart corrupts the gate. This is the canonical case for the durable workflow engine (ADR-002 pending) plus idempotency keys on the comment write. The checkpoint is a durable wait, not a polling loop.
- §4.2 dual approval path (Linear 👍 reaction *or* dashboard button) means two event sources resolve one gate; both must converge on the same workflow signal and both must record the actor (§4.2 "logged with actor"). Race: reaction and button click near-simultaneously — the workflow signal must be idempotent on first-resolution-wins.
- §4.6 craw self-flagging "risky" (large diff / sensitive path) overrides the auto-approve policy; risky always requires human review. This means the craw's plan output must carry a structured risk verdict, not free text — the policy engine reads a field, not the prose. Sensitive-path detection overlaps the file-path allow/deny lists (TRACK-14, O2.8).
- §4.1 plan must include estimated token cost; that estimate feeds the §5.6 per-task budget cap (TRACK-5) — the estimate and the enforced cap should use the same cost model (`budget.ts`) so a plan can't promise a cost the cap will then breach mid-run.
- §4.5 auto-approval still leaves the merge gate (TRACK-8 gate 2) intact; the two gates are independent. Auto-approving the plan must not auto-approve the merge — keep the gate states orthogonal in the workflow.
- §4.7 SLA default 4h with second-timeout escalation: the timer must be durable (survives restart) and cancel cleanly on approval to avoid a phantom escalation after a late approve. Open question: does SLA pause overnight / off-hours, or run wall-clock? Not specified — affects escalation noise.
