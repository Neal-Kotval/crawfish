# TRACK-9 — PR-comment loop (auto-respond with budget)

## Overview
The post-submission revision loop: the bot re-engages on @-mention (or per-repo mode), addresses review feedback through a comment-resolution state machine, caps revisions and token spend per PR, and halts honestly when it detects conflicting reviewers or out-of-scope asks. Every revision is audited. Primary personas: IC (mentions, vetoes, reads honest fallbacks), EM (per-repo mode + caps), VPE (audit). Sits after PR submission (TRACK-8); it is the only surface where the craw acts on free-form human feedback, so the budget and halt heuristics are the safety envelope.
Source: ORCHESTRATOR-USER-STORIES.md §9.

---

## User stories

9.1 **[IC]** When I @-mention `@crawfish-bot` in a PR comment, the craw re-engages to address my feedback. *AC: mention-only is the default mode; bot doesn't react to unmentioned comments.*

9.2 **[EM]** Configure auto-respond mode per repo: `mention-only`, `respond-to-all`, or `off`. *AC: mode is per repo, not per workspace; defaults to mention-only.*

9.3 **[IC]** When the bot re-engages, it posts a "working on it" reply with an estimated cost and ETA. *AC: estimated cost is based on the craw's historical revision cost.*

9.4 **[EM]** Cap the auto-respond loop per PR: max N revisions OR max $M tokens, whichever first; on cap, the bot halts and notifies. *AC: caps editable per repo; defaults: 5 revisions, $10; halt notification uses §13 channels.*

9.5 **[IC]** When the bot detects conflicting feedback across two reviewers, it halts and pings a human instead of guessing which to follow. *AC: detection is a heuristic (semantic similarity check + reviewer count); false negatives are OK; false positives waste tokens.*

9.6 **[IC]** When the bot can't address a comment (out-of-scope, requires architecture decision, ambiguous), it replies with an honest "I can't address this without X" and stops. *AC: explicit fallback path; the bot does not silently give up.*

9.7 **[VPE]** Audit log entry for every bot revision: who asked for it, what was changed, tokens spent. *AC: same audit surface as §14.*

9.8 **[IC]** I can "veto" the bot mid-loop with a comment like `@crawfish-bot halt` and the bot stops within 30s. *AC: keyword commands documented and stable.*

---

## Coding tasks (from ROADMAP.md)

- **O4.1** — Bot identity + mention listener (`cloud/server/src/orchestrator/pr-bot/listener.ts`) — implements §9.1 (@-mention re-engage) and §9.8 (`@crawfish-bot halt` veto, stop <30s).
- **O4.2** — Comment-resolution state machine (`cloud/server/src/orchestrator/pr-bot/state-machine.ts`) — drives the re-engage→revise→post cycle and §9.3 "working on it" reply.
- **O4.3** — Per-PR revision + token cap (defaults: 5 revisions, $10) (shared with O4.2) — implements §9.4.
- **O4.4** — Conflict-with-reviewer detector (`cloud/server/src/orchestrator/pr-bot/conflict-detector.ts`) — implements §9.5 (semantic-similarity + reviewer-count heuristic, halt + ping).
- **O4.5** — Out-of-scope detector (`cloud/server/src/orchestrator/pr-bot/scope-detector.ts`) — implements §9.6 honest "I can't address this without X" fallback.
- **O4.6** — Auto-respond mode toggle (mention-only / respond-to-all / off) (dashboard) — implements §9.2 per-repo mode.
- **O4.7** — Bot reply templates (standardized) (`cloud/server/src/orchestrator/pr-bot/templates.ts`) — backs §9.3, §9.6 reply shapes.
- **O4.8** — Audit trail per revision (reuses existing JSONL audit substrate) — implements §9.7 (who asked, what changed, tokens spent).

Note: §9.4 halt notification uses §13 channels (O6.4, TRACK-13); §9.7 audit shares the §14 surface (O5.3, TRACK-14). Both are cross-surface dependencies, not duplicated here.

---

## Tech stack considerations

- §9.5 conflict detector is explicitly heuristic (semantic similarity + reviewer count) with an asymmetric error budget: false negatives are acceptable, false positives waste tokens. Tune toward under-flagging. This is the one place the spec inverts the usual precision/recall preference — encode it in the threshold default, not just docs.
- §9.4 dual cap (N revisions OR $M tokens, whichever first; defaults 5 / $10) shares the bounded-retry shape with the CI fix loop (TRACK-7, §7.3). The token cap reads the same `budget.ts` model as the per-task cap (TRACK-5 §5.6); a PR-comment loop's spend should count against the same envelope the originating task used, or the per-org daily cap (TRACK-12) can be bypassed via comment churn. Open question: is comment-loop spend a fresh budget or a continuation of the task budget?
- §9.8 veto must stop the bot within 30s mid-loop — this is the same fast-cancel requirement as §5.3, and the state machine (O4.2) must check for the halt signal between revision steps, not only at boundaries. Keyword commands (§9.8) must be stable/documented since reviewers type them by hand.
- §9.1 mention-only default means the listener (O4.1) filters on bot identity; `respond-to-all` mode (§9.2) is per-repo and materially raises token spend — the cap (§9.4) is the backstop that makes respond-to-all safe to offer.
- §9.3 cost/ETA estimate is based on the craw's *historical* revision cost — this reads the per-craw stats engine (TRACK-10, `stats.ts`). A new craw with no history has no estimate; the reply template (O4.7) needs a no-data variant.
- §9.7 per-revision audit (who/what/tokens) reuses the JSONL substrate; the revision audit and the §8 merge events must share one trail so a PR's full lifecycle (plan → execute → CI → merge → comment-revisions) is reconstructable from one log.
