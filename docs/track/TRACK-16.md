# TRACK-16 — Integrations & edge cases

## Overview
The resilience and lifecycle edges: emergency GitHub-App bypass, direct-push conflict detection, GitHub and LLM-provider outage handling with automatic resume, cross-tracker migration (GitHub Issues ↔ Linear) without losing history, and subscription cancellation with a 90-day export-then-delete contract. Primary personas: PLAT (bypass, outage handling, tracker migration), IC (direct-push conflict), VPE (cancellation). This surface is where the orchestrator proves it degrades gracefully — most stories are failure-mode contracts rather than features, backed by the operational deliverables of O5–O6.
Source: ORCHESTRATOR-USER-STORIES.md §16.

---

## User stories

16.1 **[PLAT]** Bypass the orchestrator for emergency: temporarily disable the GitHub App on a repo without losing config. *AC: re-enable restores config; no data loss.*

16.2 **[IC]** If I push directly to a craw's branch while it's working, the orchestrator detects the conflict and halts. *AC: halt posts a comment explaining; ticket returns to backlog with a "human-took-over" label.*

16.3 **[IC]** If GitHub goes down or rate-limits us, queued tasks pause and resume automatically when GitHub recovers. *AC: orchestrator backs off exponentially; no false failures attributed to the craw.*

16.4 **[PLAT]** If a connected LLM provider has an outage, the task halts gracefully (saves state) and resumes when the provider recovers. *AC: durable workflow engine handles this natively (rationale for the §1.2 ADR in the stages doc).*

16.5 **[EM]** Migrate from GitHub Issues to Linear (or vice versa) without losing historical craw activity. *AC: cross-tracker links preserved; reports stitch across both.*

16.6 **[VPE]** Cancel my subscription; data exports for 90 days post-cancel; then deletion. *AC: standard SaaS deletion contract; exportable formats; explicit deletion confirmation.*

---

## Coding tasks (from ROADMAP.md)

- **O5.7** — Invite flow polish (existing `cloud/server` Invite model + new UI) — supports the multi-user lifecycle this surface's admin actions sit in.
- **O6.5** — Support runbooks (`docs/orchestrator/support/{onboarding,common-failures,billing-questions}.md`) — the operational documentation for the edge cases below.
- **O6.6** — Status page (hosted, statuspage.io or equivalent) — surfaces the GitHub/LLM-provider outages of §16.3/§16.4 to customers.
- **O6.7** — First-line on-call rotation (internal — 1 engineer/week for 10–20 customer fleet) — the human side of outage and edge-case handling.
- **O6.8** — Customer feedback channel (shared Linear/Slack per design partner) — where edge-case reports land.

Gap / flag: this is the weakest 1:1 mapping. The canonical map assigns O5.7 + O6.5–O6.8 (invite polish, runbooks, status page, on-call, feedback) — these are **operational/support** deliverables, but the **engineering** behind §16.1–§16.6 lives in other O-stages:
- §16.2 direct-push conflict halt → **O3.8** manual-takeover detection (TRACK-11); same push-watcher, conflict variant.
- §16.3 GitHub outage backoff + resume and §16.4 LLM-provider outage halt-and-resume → the **durable workflow engine** (O0.1 ADR-002 / O0.2); §16.4 AC explicitly says "durable workflow engine handles this natively (rationale for the §1.2 ADR)."
- §16.1 GitHub-App emergency disable (config-preserving) → no numbered deliverable; closest is the kill switch (O5.9, TRACK-14) but that pauses craw activity, not the GitHub App connection. **Unmapped.**
- §16.5 cross-tracker migration (GitHub Issues ↔ Linear, history-preserving) → no numbered deliverable; the GitHub mirror (`github-issues.ts`) and Linear adapter (O1.1) exist but bidirectional migration with link-stitching is unbuilt. **Unmapped.**
- §16.6 cancellation + 90-day export-then-delete → no numbered deliverable; billing (O5.1) handles subscription cancel but the data-export + deletion contract is unbuilt. **Unmapped.**
Lead should reconcile: the support deliverables (O5.7, O6.5–O6.8) are correctly here, but §16.1, §16.5, §16.6 need engineering O-stages assigned.

---

## Tech stack considerations

- §16.3 and §16.4 are the strongest argument for the durable workflow engine (ADR-002, O0.1): both require a task to pause on an external outage and resume on recovery without a false failure or a duplicate side-effect. §16.4 AC names this as the ADR's rationale. Exponential backoff (§16.3) is engine-level retry policy, not per-craw code.
- §16.2 direct-push conflict shares its push-watcher with the manual-takeover detection (O3.8, TRACK-11 §11.3); the distinction is intent — §11.3 is a deliberate graceful handoff (orchestrator exits, links human PR), §16.2 is an unexpected mid-run conflict (halt + "human-took-over" label + backlog). One watcher, two outcomes keyed on run state.
- §16.1 GitHub-App emergency disable must preserve config — re-enable restores it, no data loss. This is a connection-state toggle distinct from the kill switch (TRACK-14 §14.4, which pauses craw dispatch); disabling the App stops webhooks entirely. The config-preservation requirement means disable is a flag, not a teardown of the integration record.
- §16.5 cross-tracker migration must preserve cross-tracker links and stitch reports across both systems — the run record must store a tracker-agnostic ticket identity with both the GitHub and Linear references, or historical craw activity orphans on migration. This is a data-model requirement that should be decided before O1 inbound adapters lock their schema, not retrofitted.
- §16.6 cancellation contract (90-day export, then deletion, explicit confirmation) intersects the audit-log retention (TRACK-14 §14.2, 90-day default) and the data-export formats (TRACK-10 §10.6 CSV). The 90-day windows for audit retention and post-cancel export coincide numerically but are different clocks — don't couple them.
- The operational deliverables (O6.5 runbooks, O6.6 status page, O6.7 on-call, O6.8 feedback) are what make the failure-mode contracts above credible to a paying customer during closed beta; they are correctly sequenced in O6 alongside the first 10–20 paying teams, but they presuppose the §16.1–§16.6 engineering exists, which (per the gaps above) it partly does not yet.
