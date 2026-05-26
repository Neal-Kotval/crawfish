# TRACK-2 — Craw library & configuration

## Overview
The curated craw catalog and its per-workspace configuration: browsing benchmarked craws, installing/uninstalling, version pinning with rollback, routing rules, per-repo restriction, and the v1.5 customer-authored forking path. Primary personas: EM (installs, configures, pins), VPE (cross-repo overview), IC (forks, v1.5). Sits between onboarding and execution — it defines *which* automation a workspace runs and on *what*.
Source: ORCHESTRATOR-USER-STORIES.md §2.

---

## User stories

2.1 **[EM]** Browse the curated craw library (8–12 craws at launch) with name, description, what tasks it handles, what languages it supports, and a published benchmark per craw. *AC: each craw card shows: success rate on Crawfish's reference bench, median tokens per task, median latency, last update.*

2.2 **[EM]** Install a craw to the workspace with a single click; uninstall just as easily. *AC: install is idempotent; uninstall doesn't delete historical run data.*

2.3 **[EM]** Pin a craw to a specific version; receive notifications when a newer version is available and review the changelog before bumping. *AC: version is per-workspace, not per-repo; rollback to the previous version available for 30 days.*

2.4 **[EM]** Define routing rules: label `dep-bump` → `dep-bumper-craw v3`; label `test-backfill` → `test-craw v2`. *AC: rules evaluated in order; first match wins; fallback to "no eligible craw" if no rule matches.*

2.5 **[EM]** Restrict a craw to specific repos (e.g., the lint-cleaner runs only on the marketing-site repo). *AC: per-craw allow/deny list; deny takes precedence.*

2.6 **[VPE]** See the full list of craws active across all repos in one screen, with the version each repo is pinned to. *AC: drift indicator if two repos pin different versions of the same craw.*

2.7 **[v1.5]** **[IC]** Fork a curated craw and customize its system prompt + skill set per the customer-authored path.

2.8 **[deferred]** Submit a craw to a public marketplace.

---

## Coding tasks (from ROADMAP.md)

- **O0.4** — First curated craw (dep-bumper) (`cli/orgctl/src/craws/dep-bumper/{craw.yaml,SKILL.md,impl.ts}`) — the reference craw the library and bench format are derived from.
- **O2.1** — test-backfill craw (`cli/orgctl/src/craws/test-backfill/`).
- **O2.2** — lint-cleaner craw (`cli/orgctl/src/craws/lint-cleaner/`) — subject of §2.5's per-repo restriction example.
- **O2.3** — type-annotator craw (`cli/orgctl/src/craws/type-annotator/`).
- **O2.7** — Per-craw routing rules UI (`cloud/platform/src/pages/RoutingRules.tsx`) — implements §2.4.
- **O2.9** — Craw version pinning + rollback (dashboard) — implements §2.3 (per-workspace pin, 30-day rollback) and §2.6 (drift indicator).
- **O2.10** — Bench fixtures per craw (`bench/craws/{dep-bumper,test-backfill,lint-cleaner,type-annotator}/`) — backs the published benchmark on each card in §2.1.
- **O7.2** — Customer-authored craw forking (`cloud/platform/src/pages/CrawEditor.tsx` + `cli/orgctl/src/craws/templates/`) — implements §2.7 `[v1.5]`.
- **O7.3** — Craw authoring docs (5-page set + `craw test` CLI) (`docs/orchestrator/authoring-craws/`).
- **O7.4** — Per-workspace craw registry (private + curated together) (extends O5.7).
  - Reuses: `craw.yaml` manifest format (GRAND_PLAN §3.17, week 17) — the per-craw config schema all curated craws share.

Note: §2.5 per-craw repo allow/deny is distinct from §14.5 per-craw *file-path* allow/deny (O2.8, TRACK-14). The repo-restriction allow/deny list in §2.5 has no separately numbered deliverable; it is routing-rule scoping under O2.7. Flag if lead wants it tracked apart.

Note: §2.8 public marketplace is `[deferred]` — no O-stage; O7.x ships private forking only (ROADMAP "out of scope": full agent synthesis is Stage 2). Correctly carries no code.

---

## Tech stack considerations

- The `craw.yaml` manifest (GRAND_PLAN §3.17) is the single config contract; routing rules, pins, repo restriction, and file-path allow/deny all key off the same manifest. Schema churn here ripples to TRACK-3 routing and TRACK-14 policy — version the manifest schema.
- §2.3 version pin is per-workspace, not per-repo, but §2.6 surfaces per-repo drift. These are consistent only if "pin" sets a workspace default that a repo can override; the data model must store both levels or the drift indicator has nothing to compare. Open question: is per-repo override a v1 capability or only the drift *read*?
- §2.1 card metrics (success rate, median tokens, median latency) come from O2.10 bench fixtures, not live customer runs — these are Crawfish's reference bench. Live per-craw stats are a separate surface (TRACK-10, O10/stats.ts). Don't conflate the two data sources.
- §2.2 uninstall must not delete historical run data; install is idempotent. This is a soft-delete / tombstone pattern on the install record, not a row delete — required so TRACK-10 analytics and TRACK-14 audit stay intact across reinstalls.
- §2.7 forking (O7.2) writes to `cli/orgctl/src/craws/templates/` and a per-workspace registry (O7.4); a forked craw must not be able to escalate beyond its parent's file-path/egress policy (TRACK-14). The CrawEditor UI needs to surface inherited policy as non-editable-downward.
- Routing is "first match wins" with a "no eligible craw" fallback (§2.4); this ordering is the same evaluation the classifier hands off to (TRACK-3 §3) — keep the rule-evaluation engine single-sourced rather than reimplemented per surface.
