# TRACK-3 — Issue intake & auto-classification

## Overview
The ingestion edge: Linear webhooks and GitHub Issues polling feed an LLM eligibility classifier that decides whether a ticket is craw-eligible, writes its decision back as a comment + label, and accepts per-ticket human overrides. Primary personas: PM (files tickets, reads eligibility), EM (tunes the classifier, configures allowlist), IC (overrides), QA/EM (re-runs). Sits immediately after the integration connects (TRACK-1) and immediately before the plan checkpoint (TRACK-4).
Source: ORCHESTRATOR-USER-STORIES.md §3.

---

## User stories

3.1 **[PM]** When I create a Linear ticket, the orchestrator reads it within 60 seconds and decides whether it's craw-eligible. *AC: webhook latency < 10s; classifier latency < 20s; eligibility decision written to the ticket as a Linear comment + a label.*

3.2 **[EM]** Configure the eligibility classifier per-workspace: which labels imply yes/no, what description shape implies eligibility, what the confidence threshold is. *AC: threshold is a number 0.0–1.0; default 0.7; below threshold = "needs human review" Linear label added.*

3.3 **[IC]** Override the classifier on any individual ticket — force-eligible or force-ineligible — and have my override persist. *AC: manual override is logged with the IC's user id; future runs respect it.*

3.4 **[PM]** When the classifier marks a ticket eligible, the ticket gets a "Craw will attempt this" comment with the chosen craw, the proposed plan, and a "decline" button I can click. *AC: decline halts the run before any code is written; one click; reason field optional.*

3.5 **[PLAT]** See the classifier's confidence distribution over the last 7 days, with explicit calls-out of borderline calls (0.6–0.8 confidence). *AC: histogram + sample list of borderline tickets; click-through to the ticket.*

3.6 **[EM]** Pull GitHub Issues on a 5-minute schedule for repos where webhooks aren't available, with the same classifier flow. *AC: dedup against already-ingested issues; respect rate limits.*

3.7 **[EM]** Configure a label allowlist as the *only* signal for eligibility (skip auto-classification entirely). *AC: when allowlist mode is on, classifier never runs; cost goes to zero per ticket; eligibility is deterministic.*

3.8 **[QA, EM]** Re-run the classifier on a closed/old ticket on demand. *AC: useful when the classifier is updated and the team wants to backfill eligibility on a backlog.*

---

## Coding tasks (from ROADMAP.md)

- **O1.1** — Linear webhook receiver (`cloud/server/src/inbound/linear.ts`) — implements §3.1 ingest path (<10s webhook latency).
- **O1.2** — GitHub Issues poller (`cloud/server/src/inbound/github-issues-poller.ts`) — implements §3.6 (5-min schedule, dedup, rate-limit respect).
- **O2.4** — Auto-classifier service (Haiku-class) (`cloud/server/src/classifier/{index,prompts,eval}.ts`) — implements §3.1 eligibility decision, §3.2 config, §3.3 override resolution.
- **O2.5** — Per-workspace eval harness (`cloud/server/src/classifier/eval-harness.ts` + dashboard) — backs §3.5 confidence distribution and §3.8 re-run/backfill.
- **O2.6** — Label-only fallback toggle (dashboard + workflow) — implements §3.7 (classifier never runs, deterministic, zero per-ticket cost).
  - Reuses: `cli/orgctl/src/inbound/{github-issues,notion-pages}.ts` — the existing inbound-adapter pattern the Linear and poller adapters follow (USER-STORIES §17, §3.1).
  - Reuses: `triage.ts` heuristic normalization — the existing pre-classifier normalization the LLM classifier layers on top of (USER-STORIES §17, §3.4).

Note: §3.4's "Craw will attempt this" comment + decline button is the front edge of the plan checkpoint and is implemented by **O1.3** (plan checkpoint, TRACK-4), not by a §3 deliverable. The decline-before-any-code-written guarantee is gate-1 behavior. Cross-reference TRACK-4.

Note: §3.3 manual-override persistence (logged with user id, respected by future runs) has no separately numbered deliverable; it is classifier-state work folded into O2.4 + the override write must land in the audit log (TRACK-14, O5.3). Flag if lead wants it numbered.

---

## Tech stack considerations

- Classifier is sized Haiku-class for the §3.1 latency budget (<20s classify) and per-ticket cost; the §3.7 allowlist mode exists precisely so cost-sensitive workspaces can drive per-ticket classification cost to zero. The threshold (§3.2) is a tunable float, default 0.7 — store per-workspace, not global.
- §3.6 poller must dedup against already-ingested issues and respect GitHub rate limits; the existing `github-issues.ts` adapter already does GitHub-state reads, so the poller is a scheduler + dedup key over that, not a new GitHub client.
- §3.3 override and §3.2 config both feed the §3.8 re-run path and the §3.5 distribution — these share the eval harness (O2.5). An override is training signal: it should land in the per-workspace eval set (overlaps TRACK-15 §15.2). Keep one eval-set store, not two.
- Webhook (§3.1) vs poll (§3.6) are two ingestion modes into one classifier; the classifier must be source-agnostic so a ticket re-run (§3.8) on an old GitHub issue and a fresh Linear webhook hit the identical decision path.
- Eligibility decision is written back as both a comment and a label (§3.1); the comment side-effect must be idempotent under workflow retry (TRACK-5 §5.1) — re-firing the classifier must not double-post. Idempotency key on the ticket+classifier-version.
- Open question: §3.2 "what description shape implies eligibility" is underspecified — is shape a heuristic in the prompt, a separate feature extractor, or learned from the eval set? Affects whether O2.4 prompts alone suffice or O2.5 must feed back into classification.
