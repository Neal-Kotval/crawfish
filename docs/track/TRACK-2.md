# TRACK-2 — Craw library & configuration

**Components:** `CLI` (primary — the craws and their manifests) · `PLAT` + `DASH` (the catalog, routing, pinning, and drift widgets)
**Source:** ORCHESTRATOR-USER-STORIES.md §2 · ROADMAP.md O-stages O0.4, O2.1, O2.2, O2.3, O2.7, O2.9, O2.10, O7.2, O7.3, O7.4

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

A **craw** is one packaged, benchmarked automation: a system prompt plus a skill set plus a manifest that says what tasks it handles, what languages it supports, and how it behaved on Crawfish's reference benchmark. The dep-bumper is a craw; the test-backfiller is a craw. This surface is the catalog where an engineering manager browses those craws, installs the ones a workspace should run, pins each to a version, and writes the routing rules that decide which craw fires on which ticket.

It sits between onboarding (TRACK-1) and execution (TRACK-5). Onboarding connects the repos and the tracker; this surface defines *which* automation runs and *on what*. Until a workspace installs at least one craw and writes one routing rule, an eligible ticket has nowhere to go — the classifier (TRACK-3) will mark it eligible and then fall through to "no eligible craw."

The split across components is sharp. The **craws themselves are CLI code** — they live in `cli/orgctl/src/craws/`, each a directory with a `craw.yaml` manifest, a `SKILL.md`, and an `impl.ts`. The **catalog, routing-rule editor, version-pin UI, and cross-repo drift view are platform/dashboard surfaces** — React pages backed by `cloud/server`, mirrored into `desktop/dash` so the same widgets render in the desktop shell. The manifest format (`craw.yaml`) is the shared contract both halves key off: GRAND_PLAN §3.17 defines it, and routing, pinning, repo-restriction, and file-path allow/deny all read the same schema.

What already exists (USER-STORIES §17): the `craw.yaml` manifest format is specified, and the inbound-adapter pattern the craws reuse is shipped. What is new is the curated craw bodies, the catalog UI, and the configuration surfaces.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Browse the curated library (§2.1) | `PLAT` + `DASH` | catalog UI backed by O2.10 bench fixtures (`bench/craws/...`) |
| Install / uninstall a craw (§2.2) | `PLAT` + `DASH` | install record in `cloud/server` (soft-delete on uninstall) |
| Version pin + rollback (§2.3) | `PLAT` + `DASH` | `O2.9` craw version pinning (dashboard) |
| Routing rules (§2.4) | `PLAT` + `DASH` | `cloud/platform/src/pages/RoutingRules.tsx` (O2.7) |
| Restrict a craw to repos (§2.5) | `PLAT` + `DASH` | routing-rule scoping under O2.7 — **see Gaps** |
| Cross-repo active-craw view + drift (§2.6) | `PLAT` + `DASH` | `O2.9` drift indicator (dashboard) |
| Fork + customize a craw (§2.7) `[v1.5]` | `PLAT` + `CLI` | `cloud/platform/src/pages/CrawEditor.tsx` + `cli/orgctl/src/craws/templates/` (O7.2) |
| Submit to a public marketplace (§2.8) | — | `[deferred]` — no code |

---

## User stories

Tags are now **components** (where it gets built), not personas.

2.1 **[PLAT, DASH]** Browse the curated craw library (8–12 craws at launch) with name, description, what tasks it handles, what languages it supports, and a published benchmark per craw. *AC: each craw card shows: success rate on Crawfish's reference bench, median tokens per task, median latency, last update.*

2.2 **[PLAT, DASH]** Install a craw to the workspace with a single click; uninstall just as easily. *AC: install is idempotent; uninstall doesn't delete historical run data.*

2.3 **[PLAT, DASH]** Pin a craw to a specific version; receive notifications when a newer version is available and review the changelog before bumping. *AC: version is per-workspace, not per-repo; rollback to the previous version available for 30 days.*

2.4 **[PLAT, DASH]** Define routing rules: label `dep-bump` → `dep-bumper-craw v3`; label `test-backfill` → `test-craw v2`. *AC: rules evaluated in order; first match wins; fallback to "no eligible craw" if no rule matches.*

2.5 **[PLAT, DASH]** Restrict a craw to specific repos (e.g., the lint-cleaner runs only on the marketing-site repo). *AC: per-craw allow/deny list; deny takes precedence.*

2.6 **[PLAT, DASH]** See the full list of craws active across all repos in one screen, with the version each repo is pinned to. *AC: drift indicator if two repos pin different versions of the same craw.*

2.7 **[v1.5]** **[PLAT, CLI]** Fork a curated craw and customize its system prompt + skill set per the customer-authored path.

2.8 **[deferred]** Submit a craw to a public marketplace.

---

## Coding tasks, by component

### CLI — `cli/orgctl` (the craws themselves)

- **O0.4** — First curated craw, the dep-bumper (`cli/orgctl/src/craws/dep-bumper/{craw.yaml,SKILL.md,impl.ts}`). The reference craw the library card format and the bench format are derived from. It is "boring & bounded" — bumping a dependency is mechanical and low-risk — which is exactly why TRACK-1's onboarding walkthrough (O6.1) runs it to produce the demo PR. Treat its three files as the template every other curated craw copies: a manifest, a skill doc, an implementation.

- **O2.1** — test-backfill craw (`cli/orgctl/src/craws/test-backfill/`). Generates missing unit tests for a target module. Same three-file shape as O0.4. Routed by the `test-backfill` label in §2.4's example.

- **O2.2** — lint-cleaner craw (`cli/orgctl/src/craws/lint-cleaner/`). Applies lint/format fixes. This is the craw §2.5 uses to illustrate per-repo restriction ("runs only on the marketing-site repo"), so its manifest must declare it as restrictable.

- **O2.3** — type-annotator craw (`cli/orgctl/src/craws/type-annotator/`). Adds type annotations to untyped code. Rounds out the launch catalog toward the 8–12 craws §2.1 promises.

- **O2.10** — Bench fixtures per craw (`bench/craws/{dep-bumper,test-backfill,lint-cleaner,type-annotator}/`). The recorded benchmark runs that back the success-rate / median-tokens / median-latency numbers on each card in §2.1. These are Crawfish's *reference* bench, not live customer runs — a fixed fixture set re-run on each craw version. Do not source the card metrics from production telemetry (that is a separate surface, TRACK-10, `stats.ts`).

  ```ts
  // bench/craws/dep-bumper/fixtures.ts — what each card metric is computed from
  export const benchResult = {
    crawVersion: "v3.1.0",
    runs: 50,                 // fixed fixture tickets re-run per version
    successRate: 0.94,        // → "success rate" on the card
    medianTokens: 18_400,     // → "median tokens per task"
    medianLatencyMs: 42_000,  // → "median latency"
    recordedAt: "2026-05-20", // → "last update"
  };
  ```

### PLAT + DASH — catalog, routing, pinning, drift

- **O2.7** — Per-craw routing rules UI (`cloud/platform/src/pages/RoutingRules.tsx`). Implements §2.4. The user builds an ordered list of `label → craw@version` rules; the engine evaluates top-down, first match wins, and falls through to "no eligible craw" if none match. The ordering is the same first-match evaluation the classifier hands off to (TRACK-3 §3) — single-source the rule-evaluation engine; do not reimplement it per surface.

  ```ts
  // Routing is ordered; first match wins; explicit fallback.
  type RoutingRule = { label: string; craw: string; version: string };
  function route(ticketLabels: string[], rules: RoutingRule[]) {
    for (const rule of rules) {                 // order is significant
      if (ticketLabels.includes(rule.label)) return rule; // first match wins
    }
    return null;                                // → "no eligible craw"
  }
  ```

- **O2.9** — Craw version pinning + rollback (dashboard). Implements §2.3 (per-workspace pin, changelog review before a bump, 30-day rollback) and §2.6 (the drift indicator across repos). A pin is a workspace-level default; the drift indicator compares each repo's effective version against that default and flags repos that diverge. Rollback means keeping the previous version installable for 30 days, not deleting it on bump.

- **O7.2** — Customer-authored craw forking (`cloud/platform/src/pages/CrawEditor.tsx` + `cli/orgctl/src/craws/templates/`). Implements §2.7 `[v1.5]`. The editor (PLAT) lets a customer copy a curated craw, edit its system prompt and skill set, and save it to a per-workspace registry; the templates it forks from live in CLI. A forked craw must not escalate beyond its parent's file-path / egress policy (TRACK-14) — the editor surfaces inherited policy as non-editable-downward.

- **O7.4** — Per-workspace craw registry, private + curated together (extends O5.7). Where a workspace's forked craws live alongside the curated catalog so install, routing, and pinning treat both uniformly. This is **PLAT + CLI**: the registry record is PLAT (Prisma), the craw bodies are CLI.

**Reuses (already shipped — do not rebuild):**
- `craw.yaml` manifest format (GRAND_PLAN §3.17, week 17) — the per-craw config schema all curated craws share. Routing rules, pins, repo restriction, and file-path allow/deny all key off this one manifest.

### Operational / docs

- **O7.3** — Craw authoring docs (`docs/orchestrator/authoring-craws/`). A 5-page set plus a `craw test` CLI command so a customer authoring a fork (O7.2) can validate it against fixtures before installing. Docs and tooling, no product surface.

**Cross-references / scope notes:**
- §2.5 per-craw *repo* allow/deny is distinct from §14.5 per-craw *file-path* allow/deny (O2.8, TRACK-14). The repo-restriction list in §2.5 has **no separately numbered deliverable** — it is routing-rule scoping under O2.7. See Gaps.
- §2.8 public marketplace is `[deferred]` — no O-stage. O7.x ships private forking only (ROADMAP "out of scope": full agent synthesis is Stage 2). Correctly carries no code.

---

## Key technical concepts, explained

**The `craw.yaml` manifest schema (GRAND_PLAN §3.17).** One YAML file per craw is the single config contract. It declares identity, capability, and the policy envelope every configuration surface reads — so routing (O2.7), pinning (O2.9), repo restriction (§2.5), and file-path policy (TRACK-14) are not four separate schemas but four readers of one.

```yaml
# cli/orgctl/src/craws/lint-cleaner/craw.yaml
id: lint-cleaner
version: 2.1.0
handles: [lint-fix, format]      # task types → drives the catalog "what it handles"
languages: [ts, js, css]
restrictable: true               # §2.5 — may be limited to specific repos
policy:                          # TRACK-14 envelope a fork cannot widen
  filePaths: { allow: ["**/*.ts", "**/*.css"], deny: ["**/secrets/**"] }
  egress: false
```

Because every surface keys off this one file, **schema churn here ripples**: a new field that routing reads must be versioned, or older manifests break the routing engine. Version the manifest schema explicitly.

**Version pin vs. per-repo drift (§2.3 vs §2.6).** A pin (§2.3) is a *workspace* default — "this workspace runs lint-cleaner v2.1.0." Drift (§2.6) is a *per-repo* read — "repo A is on v2.1.0 but repo B is still on v2.0.0." These are only consistent if the data model stores both levels: a workspace pin and an optional per-repo override. If only the workspace pin is stored, the drift indicator has nothing to compare against and the §2.6 AC cannot be met. (Open question below: is per-repo *override* a v1 capability, or only the drift *read*?)

**Soft-delete on uninstall (§2.2 AC).** Uninstall must not delete historical run data — TRACK-10 analytics and TRACK-14 audit both depend on it staying intact across reinstalls. So uninstall is a tombstone, not a row delete, and install is idempotent (a second install of an already-installed craw returns the same record, optionally clearing the tombstone).

```ts
// Uninstall = soft-delete; reinstall = idempotent upsert that clears the tombstone.
await db.crawInstall.update({ where: { id }, data: { uninstalledAt: new Date() } });
// historical runs keyed to this install row remain queryable.

await db.crawInstall.upsert({
  where: { workspaceId_crawId: { workspaceId, crawId } },
  create: { workspaceId, crawId },
  update: { uninstalledAt: null },   // reinstall revives the same row
});
```

---

## Gaps — work with no O-stage assigned

These stories have acceptance criteria but **no numbered O0–O7 deliverable.** Flag for the lead.

- **§2.5 per-craw repo allow/deny list.** No separately numbered deliverable; it currently rides as routing-rule scoping under O2.7. This is distinct from §14.5's per-craw *file-path* allow/deny (O2.8, TRACK-14) — different granularity. *What's needed:* either confirm O2.7 owns the repo allow/deny with "deny takes precedence," or split it into its own deliverable so it has its own bench and audit hooks.
- **§2.6 per-repo version override storage.** The drift indicator (O2.9) needs both a workspace pin and a per-repo effective version to compare. If per-repo override is not a stored capability, drift can only ever read identical values and never flag. *What's needed:* a decision on whether v1 stores per-repo overrides or only reads drift from some other signal (see Open questions).

---

## Open questions

- **§2.3 / §2.6 per-repo override:** is per-repo version override a v1 capability, or does v1 only ship the drift *read* (workspace pin only, no override)? This decides whether O2.9's data model carries a per-repo layer.
- **§2.5 scoping ownership:** does the lead want repo allow/deny tracked apart from O2.7, or folded into it? Affects whether it gets its own bench fixture and audit trail.
- **§2.7 fork policy inheritance:** the CrawEditor must surface inherited file-path/egress policy as non-editable-downward (a fork cannot widen its parent's envelope). Confirm the enforcement point is the manifest validator, not just the UI — UI-only enforcement is bypassable via the CLI.
