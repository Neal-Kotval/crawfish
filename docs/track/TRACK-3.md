# TRACK-3 — Issue intake & auto-classification

**Components:** `PLAT` (primary — ingest receivers, classifier, config + eval surfaces) · `PLAT` + `DASH` (the fallback toggle and confidence-distribution widget) · reuses `CLI` inbound adapters + `triage.ts`
**Source:** ORCHESTRATOR-USER-STORIES.md §3 · ROADMAP.md O-stages O1.1, O1.2, O2.4, O2.5, O2.6

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the ingestion edge. A ticket is created in Linear or filed as a GitHub Issue; within seconds the orchestrator reads it, runs an LLM classifier to decide whether it is *craw-eligible*, and writes that decision back onto the ticket as a comment plus a label. A human can override the decision on any single ticket, and the override sticks.

In the request lifecycle it sits immediately after the integration is connected (TRACK-1) and immediately before the plan checkpoint (TRACK-4). Eligibility is the gate that turns a raw ticket into something the orchestrator will attempt — without it, every ticket would either be ignored or naively attempted.

Almost all of this is **PLAT**. The two ingest receivers (`linear.ts` webhook, `github-issues-poller.ts`), the classifier service, the per-workspace classifier config, the eval harness, and the label-only fallback all live in `cloud/server`. Two pieces also have a **dashboard half**: the confidence-distribution view (§3.5) and the label-only toggle (§3.7) render in both `cloud/platform` and `desktop/dash`.

What already exists (USER-STORIES §17): the **CLI inbound-adapter pattern** (`cli/orgctl/src/inbound/{github-issues,notion-pages}.ts`) is shipped — the Linear receiver and the poller follow it rather than inventing a new GitHub client — and **`triage.ts`** already does heuristic normalization that the LLM classifier layers on top of. What is new is the webhook receiver, the LLM classifier, and the config + eval surfaces.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Read a Linear ticket within 60s, decide eligibility (§3.1) | `PLAT` | `cloud/server/src/inbound/linear.ts` (O1.1) → classifier (O2.4) |
| Configure the classifier per-workspace (§3.2) | `PLAT` | `cloud/server/src/classifier/{index,prompts,eval}.ts` (O2.4) |
| Per-ticket human override (§3.3) | `PLAT` | classifier-state in O2.4; override write lands in audit log (TRACK-14, O5.3) |
| "Craw will attempt this" comment + decline (§3.4) | `PLAT` | **O1.3** plan checkpoint, TRACK-4 — not a §3 deliverable |
| Confidence distribution over 7 days (§3.5) | `PLAT` | `cloud/server/src/classifier/eval-harness.ts` + dashboard (O2.5) |
| Poll GitHub Issues every 5 min (§3.6) | `PLAT` | `cloud/server/src/inbound/github-issues-poller.ts` (O1.2) |
| Label-allowlist-only mode (§3.7) | `PLAT` + `DASH` | label-only fallback toggle (O2.6) |
| Re-run classifier on an old ticket (§3.8) | `PLAT` + `DASH` | eval harness re-run (O2.5) |

---

## User stories

Tags are now **components** (where it gets built), not personas.

3.1 **[PLAT]** When I create a Linear ticket, the orchestrator reads it within 60 seconds and decides whether it's craw-eligible. *AC: webhook latency < 10s; classifier latency < 20s; eligibility decision written to the ticket as a Linear comment + a label.*

3.2 **[PLAT]** Configure the eligibility classifier per-workspace: which labels imply yes/no, what description shape implies eligibility, what the confidence threshold is. *AC: threshold is a number 0.0–1.0; default 0.7; below threshold = "needs human review" Linear label added.*

3.3 **[PLAT]** Override the classifier on any individual ticket — force-eligible or force-ineligible — and have my override persist. *AC: manual override is logged with the IC's user id; future runs respect it.*

3.4 **[PLAT]** When the classifier marks a ticket eligible, the ticket gets a "Craw will attempt this" comment with the chosen craw, the proposed plan, and a "decline" button I can click. *AC: decline halts the run before any code is written; one click; reason field optional.*

3.5 **[PLAT, DASH]** See the classifier's confidence distribution over the last 7 days, with explicit calls-out of borderline calls (0.6–0.8 confidence). *AC: histogram + sample list of borderline tickets; click-through to the ticket.*

3.6 **[PLAT]** Pull GitHub Issues on a 5-minute schedule for repos where webhooks aren't available, with the same classifier flow. *AC: dedup against already-ingested issues; respect rate limits.*

3.7 **[PLAT, DASH]** Configure a label allowlist as the *only* signal for eligibility (skip auto-classification entirely). *AC: when allowlist mode is on, classifier never runs; cost goes to zero per ticket; eligibility is deterministic.*

3.8 **[PLAT, DASH]** Re-run the classifier on a closed/old ticket on demand. *AC: useful when the classifier is updated and the team wants to backfill eligibility on a backlog.*

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O1.1** — Linear webhook receiver (`cloud/server/src/inbound/linear.ts`). Implements the §3.1 ingest path with its <10s webhook latency budget. Linear POSTs a payload on every ticket event; the handler must **verify the HMAC signature** before trusting it (see concepts below), normalize the event through `triage.ts`, then hand the ticket to the classifier. The receiver is push-based and source-tagged so a re-run (§3.8) hits the identical decision path as a fresh hit.

- **O1.2** — GitHub Issues poller (`cloud/server/src/inbound/github-issues-poller.ts`). Implements §3.6: poll the Issues API on a 5-minute schedule for repos where no webhook is available. Because the shipped `github-issues.ts` adapter already does GitHub-state reads, the poller is a scheduler plus a **dedup key** over that adapter — not a new GitHub client — and it must respect GitHub's rate limits.

  ```ts
  // github-issues-poller.ts — dedup so the same issue isn't ingested twice across polls
  const seen = await db.ingestedIssue.findUnique({
    where: { repoId_issueNumber_updatedAt: { repoId, issueNumber, updatedAt } },
  });
  if (seen) return;                 // already ingested at this updatedAt → skip
  await classify(normalize(issue)); // same classifier path as the Linear webhook
  await db.ingestedIssue.create({ data: { repoId, issueNumber, updatedAt } });
  ```

- **O2.4** — Auto-classifier service, Haiku-class (`cloud/server/src/classifier/{index,prompts,eval}.ts`). The core of this surface. Implements §3.1's eligibility decision, §3.2's per-workspace config (label yes/no signals, description-shape signal, confidence threshold), and §3.3's override resolution. Sized Haiku-class to meet the <20s latency budget and keep per-ticket cost low. Source-agnostic: a Linear webhook and a re-run on an old GitHub issue must produce the identical decision.

- **O2.5** — Per-workspace eval harness (`cloud/server/src/classifier/eval-harness.ts` + dashboard). Backs §3.5's 7-day confidence distribution and §3.8's on-demand re-run / backlog backfill. An override (§3.3) is training signal — it should land in the per-workspace eval set (this overlaps TRACK-15 §15.2). Keep **one** eval-set store, not two: the distribution view, the re-run path, and the override-as-signal all read and write the same set.

- **O2.6** — Label-only fallback toggle (dashboard + workflow). Implements §3.7. When allowlist mode is on, the classifier never runs: eligibility is purely "does the ticket carry a label on the allowlist," which is deterministic and drives per-ticket classification cost to zero. The toggle is **PLAT + DASH** — the switch and the workflow branch are server-side, the control renders in both `cloud/platform` and `desktop/dash`.

  ```ts
  // O2.6 — allowlist mode short-circuits the LLM entirely
  if (workspace.classifierMode === "allowlist") {
    const eligible = ticket.labels.some((l) => workspace.allowlist.includes(l));
    return { eligible, confidence: 1.0, cost: 0 }; // deterministic, zero LLM cost
  }
  return await classifier.run(ticket); // O2.4 LLM path
  ```

**Reuses (already shipped — do not rebuild):**
- `cli/orgctl/src/inbound/{github-issues,notion-pages}.ts` — the inbound-adapter pattern the Linear receiver and the poller follow (USER-STORIES §17, §3.1). The adapters are **CLI**; the receivers wrap them in `cloud/server`.
- `triage.ts` heuristic normalization (**CLI**) — the pre-classifier normalization the LLM classifier layers on top of (USER-STORIES §17, §3.4). The classifier does not re-derive what triage already extracted.

**Cross-references / scope notes:**
- §3.4's "Craw will attempt this" comment + decline button is the front edge of the plan checkpoint, implemented by **O1.3** (plan checkpoint, TRACK-4), not by a §3 deliverable. The decline-before-any-code-written guarantee is gate-1 behavior. See TRACK-4.
- §3.3 manual-override persistence (logged with user id, respected by future runs) has **no separately numbered deliverable**; it is classifier-state work folded into O2.4, and the override write must also land in the audit log (TRACK-14, O5.3). See Gaps.

---

## Key technical concepts, explained

**Webhook signature verification (§3.1).** Linear (and GitHub) sign every webhook payload with an HMAC of the request body using a shared secret. If you skip verification, anyone who learns your public URL can POST fake tickets and trigger craw runs. Verify before parsing, and use a constant-time compare so the check itself doesn't leak the secret via timing.

```ts
// linear.ts — reject anything not signed with our secret, in constant time
import crypto from "crypto";
const expected = crypto.createHmac("sha256", WEBHOOK_SECRET)
  .update(rawBody).digest("hex");
const got = req.header("linear-signature") ?? "";
if (!crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(got))) {
  return res.status(401).end();      // not really Linear → drop it
}
```

**Classifier confidence threshold (§3.2).** The classifier returns a float in 0.0–1.0. The per-workspace threshold (default 0.7) is the cut: at or above, the decision stands; below, the ticket gets a "needs human review" label instead of an automatic yes/no. The 0.6–0.8 band is the "borderline" range §3.5 surfaces explicitly so a team can audit the calls the classifier was least sure about. The threshold is **per-workspace, stored, tunable** — not a global constant.

```ts
const { eligible, confidence } = await classifier.run(ticket);
if (confidence < workspace.threshold) {        // default 0.7
  await linear.addLabel(ticket.id, "needs human review");
} else {
  await writeDecision(ticket, { eligible, confidence }); // comment + label (§3.1)
}
```

**Dedup key + idempotent write-back (§3.6, §3.1).** Two independent dedup concerns. The poller must not ingest the same issue twice across polls — key on `(repo, issueNumber, updatedAt)`. And the eligibility *write-back* (comment + label) must be idempotent under workflow retry (TRACK-5 §5.1): re-firing the classifier must not double-post the comment. Key the comment side-effect on `(ticketId, classifierVersion)` so a retry recognizes the comment already exists.

```ts
// idempotent comment: one comment per (ticket, classifier version)
await db.classifierComment.upsert({
  where: { ticketId_classifierVersion: { ticketId, classifierVersion } },
  create: { ticketId, classifierVersion, externalCommentId: await postComment() },
  update: {}, // already posted → no second comment on retry
});
```

---

## Gaps — work with no O-stage assigned

These stories have acceptance criteria but **no numbered O0–O7 deliverable.** Flag for the lead.

- **§3.3 manual-override persistence.** No separately numbered deliverable. It is classifier-state work folded into O2.4, but the override must (a) persist keyed to the ticket, (b) be respected by future runs, and (c) write to the audit log (TRACK-14, O5.3) with the actor's user id. *What's needed:* confirm O2.4 owns override state and that the audit write is wired, or number it separately so it gets its own test coverage.

---

## Open questions

- **§3.2 "what description shape implies eligibility"** is underspecified — is "shape" a heuristic baked into the classifier prompt, a separate feature extractor, or something learned from the eval set? This decides whether O2.4 prompts alone suffice or O2.5 must feed back into classification.
- **§3.3 override as training signal:** an override lands in the per-workspace eval set (overlaps TRACK-15 §15.2). Confirm there is one eval-set store shared by the distribution view (§3.5), the re-run path (§3.8), and override capture — not two stores that drift.
- **§3.1 / §3.6 source-agnostic decision path:** a re-run (§3.8) on an old GitHub issue and a fresh Linear webhook must hit the identical decision path. Confirm the classifier input is fully normalized by `triage.ts` so no source-specific branch leaks into O2.4.
