## Cross-Cutting — Architecture Audit

Scope: seams between tiers (cloud / desktop / cli / ui / web) and whole-repo
structural health. Read-only. Per-tier internals are covered by other agents.

Evidence base: `.planning/{ROADMAP,PROJECT,STATE}.md`, `docs/roadmap/GRAND_PLAN.md`,
`docs/specs/org-contract.md`, the Prisma schema, the three onboarding code paths,
and the actual `Task`/`Org`/`Issue` type definitions across all four tiers.

### Findings table

| Severity | Area | Finding | Roadmap phase(s) threatened | Recommendation | Cite |
|---|---|---|---|---|---|
| BLOCKER | Workflow engine | **ADR-002 (durable workflow engine: Temporal vs Inngest vs Restate) is OPEN.** It is the first success-criterion of Phase 12 (O0) and gates the entire M3 Orchestrator track (Phases 12–19). No `cloud/server/src/orchestrator/` skeleton exists yet. Until ADR-002 lands, none of M3 can be planned concretely. | 12–19 (all of M3) | Author + ratify ADR-002 before any M3 phase is planned. It also blocks the 6 listed O0 open questions (host, token ceiling, single-vs-per-customer GitHub App). Treat M3 planning as gated. | `.planning/STATE.md` Blockers; `.planning/ROADMAP.md` Phase 12 SC#1; `PROJECT.md` Key Decisions |
| HIGH | Org/board/issue model | **Three incompatible `TaskStatus` enums exist for the same conceptual board.** `cli/orgctl` + `desktop/dash/web` use `"backlog"\|"in_progress"\|"review"\|"done"`; `cli/projectctl` uses `"todo"\|"doing"\|"done"\|"blocked"`; `cloud/server` `Issue.state` normalizes to `"open"\|"closed"`. No shared type, no mapping layer. See dedicated section. | 7, 13, 20 | Define a single canonical status vocabulary in a shared package (or the contract) and a documented projection function per surface. | `cli/orgctl/src/board.ts:11`; `cli/projectctl/src/tasks.ts:35`; `desktop/dash/web/src/lib/board.ts:4`; `cloud/server/prisma/schema.prisma:152` |
| HIGH | Org/board/issue model | **Two parallel on-disk board systems with overlapping-but-divergent event vocabularies.** `cli/orgctl` writes the **org** board (`~/.crawfish/orgs/<id>/board.jsonl`, folded `FoldedTask`); `cli/projectctl` writes the **project** board (`<repo>/.crawfish/board.jsonl`, canonical `.md` + rebuildable jsonl per ADR-001 Option C). `projectctl`'s `ProjectBoardEventType` has ~21 event kinds incl. `task_status_changed`, `task_renamed`; orgctl's `BoardEvent` folds differently. They are kept "aligned" only by a hand-copied comment, not a shared type. | 7, 8, 11 | Decide whether org-board and project-board are the same substrate or two; if two, write the explicit relationship in `org-contract.md`. They will drift. | `cli/projectctl/src/project-board.ts:1-40`; `cli/orgctl/src/board.ts:45-160` |
| HIGH | Onboarding | **Three independent org-creation paths that produce different shapes.** (1) cloud `OnboardingFlow.tsx` 5-stage wizard POSTs `/api/orgs`; (2) cloud `lib/workspace.ts::ensureUserHasWorkspace` auto-provisions one org/user on first sign-in; (3) dash `wizards/describe/index.tsx` runs a *stubbed* `synthesize()` with no router push. All three hardcode their own copy of `DEFAULT_AGENTS`. None create a board. See onboarding section. | 1, 2, 18, 20 | Consolidate the default-agent set into one shared definition; decide which path is authoritative; have at least one path seed an initial board (GRAND_PLAN §3.1 promises "synthesizes … initial board"). | `cloud/platform/src/onboarding/OnboardingFlow.tsx`; `cloud/server/src/lib/workspace.ts`; `desktop/dash/web/src/wizards/describe/index.tsx` |
| HIGH | Repo hygiene | **`cli/orgctl/dist/` and `dist-test/` are committed to git (24 tracked files) and the umbrella `.gitignore` has no `dist` rule.** Lens/dash submodules correctly gitignore `dist` + `web/dist`, but the in-tree CLI does not. Committed build output is exactly the parallel-agent-team clobber hazard CLAUDE.md warns against, and the current `git status` already shows 6 modified/untracked `dist*` files. | any agent-team fanout (C2.P1.M3, P2, P3) | Add `dist/` and `dist-test/` to umbrella `.gitignore`; `git rm -r --cached cli/orgctl/dist cli/orgctl/dist-test`. Build artifacts must not be tracked. | umbrella `.gitignore` (no dist rule); `git ls-files cli/orgctl/dist*` = 24 |
| MED | Submodule integrity | **`desktop/lens` submodule pointer is on branch `wk5/stage1-now`, not `main`.** `desktop/dash` is on `main`. A detached/feature-branch submodule pointer means a fresh `git submodule update` may land teammates on inconsistent lens code; the umbrella records a commit, not the branch. | C2.P1.M3 diagnoses fanout; any lens-touching phase | Confirm intended lens pin; merge `wk5/stage1-now` → `main` or pin umbrella to a `main` commit before spawning lens teammates. | `git submodule status` → `ab46e89 desktop/lens (heads/wk5/stage1-now)` |
| MED | UI single-source | **`ui/tokens/globals.css` IS the only `.css` in the tree (good), but the dash test config aliases `@crawfish/ui` to a different path than its build config.** `vite.config.ts` resolves `../../../ui` (3 levels); `vitest.config.ts` resolves `../../ui` (2 levels). One of them resolves to the wrong directory; tests and build see different `@crawfish/ui`. | 1, 3 (dash MVP + hardening), any UI phase | Reconcile the dash `vitest.config.ts` alias to match `vite.config.ts` (`../../../ui`). Verify imports resolve under test. | `desktop/dash/web/vite.config.ts:16` (`../../../ui`) vs `desktop/dash/web/vitest.config.ts:9` (`../../ui`) |
| MED | Org/board/issue model | **Cloud `Org`/`OrgMember` role vocabulary diverges from the on-disk ACL vocabulary.** Cloud `OrgMember.role` = `founder\|contributor\|viewer` and `Invite.role` = `owner\|contributor`; on-disk `MemberAcl` (lens) = `owner\|admin\|member\|viewer`. The same "member" concept has three role lexicons that don't map 1:1. | 4 (Member ACL), 17 (RBAC), 20 | Define one role→ACL mapping table in `org-contract.md`; reconcile `Invite.role` vs `OrgMember.role` (already inconsistent inside cloud alone). | `cloud/server/prisma/schema.prisma` (OrgMember/Invite); `desktop/lens/src/server/types.ts` `MemberAcl` |
| MED | Org/board/issue model | **Cloud `Issue` (Postgres) and on-disk `Task` (jsonl) have no reconciliation layer despite Phase 20's milestone note declaring `Issue` "the source of truth that Phase 13's webhook/poller can later feed."** `Issue.provider` includes `"native"`, hinting at convergence, but there is no code mapping `Issue` ↔ `board.jsonl` `task_created`, and no `externalId`/external-ref on the on-disk Task. | 13, 20 | Specify the `Issue`→`board.jsonl` projection (and the `native` round-trip) in the contract *before* Phase 13/20, or the "source of truth" claim is aspirational. | `cloud/server/prisma/schema.prisma:152` (`Issue`); no external-ref field in `cli/orgctl/src/board.ts` FoldedTask |
| MED | DB substrate | **Prisma datasource is `sqlite` with a `// swap to postgresql for prod` comment, but Phase 20 success criteria say "Postgres `Issue` model" and "the migration applies cleanly."** sqlite-specific shapes are already baked in (`labels String // sqlite has no array/JSON type`). A late sqlite→Postgres swap will require migration rework. | 17, 20 | Decide the prod DB now; if Postgres, switch the datasource and stop encoding sqlite limitations (JSON-string `labels`) into the schema. | `cloud/server/prisma/schema.prisma:7-9`, `:152` comment |
| LOW | Repo hygiene | **Many untracked build/artifact dirs in working tree** (`web/dist/`, `cli/orgctl/dist/preflight.js[.map]`, `cli/orgctl/dist/templates/`, `cli/orgctl/dist/tools/`, `desktop/dash` modified pointer). Noise that makes `git status` unreliable for teammates and risks accidental commits of generated output. | agent-team fanout | After the `.gitignore` fix, clean the tree; ensure no generated dir is tracked. | `git status --porcelain` |
| LOW | Naming | **`crawfish-dash` / `crawfish-lens` root symlinks → `desktop/{dash,lens}`** exist (untracked) and are referenced by old GRAND_PLAN paths (`crawfish-dash/src/templates/`, `crawfish-lens/src/server/`). Convenience shims for pre-pivot paths, but they create two valid paths to the same code — a footgun for ownership rules keyed on `desktop/...`. | C2.* fanouts (ownership keyed on `desktop/`) | Keep as untracked dev convenience or remove; never let ownership/registry rules reference the symlink path. | `crawfish-dash -> desktop/dash`, `crawfish-lens -> desktop/lens` |

### The org/board/issue model coherence problem across tiers

This is the central architectural risk. The single conceptual triple
("org", "board/task/issue", "member") has **fractured into multiple
non-reconciled definitions** as the project pivoted from observability to
agent-org platform. Inventory:

**"Org" — 3 definitions, partially mapped:**
1. On-disk org (`~/.crawfish/orgs/<ULID>/org.json`) — the contract's canonical
   org (`org-contract.md` §1–2). ULID id, members as `.md` files.
2. Cloud `Org` (Postgres, `schema.prisma:21`) — `cuid()` id, `name @unique`
   "matches the on-disk folder name". So the join key between cloud and disk is
   the **org name string**, not a shared id. Fragile (rename breaks it; the
   onboarding slug sanitizer can collide and append `-2`).
3. Cloud `AgentMeta` is explicitly "mirrored from the Dash on-disk org" —
   confirming the disk is upstream of cloud for agents, but cloud is upstream
   for `Issue`. Bidirectional source-of-truth with no arbiter.

**"Board / task / issue" — 4 definitions, 3 status vocabularies, 0 shared type:**
1. **orgctl board** (`cli/orgctl/src/board.ts`): `FoldedTask`, statuses
   `backlog|in_progress|review|done`, append-only `board.jsonl`, folded.
2. **dash board** (`desktop/dash/web/src/lib/board.ts`): re-declares its own
   `Task`, `BoardEvent`, `TaskStatus` (same 4 values as orgctl — a *copy*, not
   an import). Drift is a matter of time.
3. **projectctl board** (`cli/projectctl/src/tasks.ts`): different model —
   `.crawfish/tasks/*.md` canonical + `.crawfish/board.jsonl` rebuildable
   (ADR-001 Option C), statuses `todo|doing|done|blocked`, ~21 event kinds in
   `ProjectBoardEventType`. A comment claims it "borrows from orgctl … so the
   vocabularies stay aligned" — but the status enums already disagree.
4. **cloud Issue** (`schema.prisma:152`): Postgres, `state open|closed`,
   `provider github|linear|native`, keyed `(projectId, provider, externalId)`.
   Phase 20's milestone note anoints this "the source of truth that Phase 13
   can feed" — yet no code maps an `Issue` to any `board.jsonl` event, and the
   on-disk Task has no `externalId`/external-ref to round-trip against.

**"Member" — 3 role lexicons:**
- on-disk/lens `MemberAcl`: `owner|admin|member|viewer`
- cloud `OrgMember.role`: `founder|contributor|viewer`
- cloud `Invite.role`: `owner|contributor`
No mapping table. ACL enforcement (`validateActor` in lens `board.ts`) uses the
4-tier lexicon; the cloud onboarding/invite path uses the others.

**Why this matters now, not later:** Phase 7 (board primitives) is the hard
prerequisite for both M2 *and* the entire M3 orchestrator track, and Phase 20
declares cloud `Issue` the source of truth Phase 13 feeds. If the board model
is still 4 divergent definitions when Phase 13 tries to wire intake→board, the
integration has no shared type to target. The org-contract (`org-contract.md`)
covers only the **org-board** (orgctl/lens) surface; it is silent on
projectctl's `.crawfish` board and on the cloud `Issue` reconciliation. The
contract is real and good, but it does not yet span the seam it most needs to.

**Recommendation:** Before Phase 7 closes, extend `org-contract.md` (or a new
`board-model.md`) to be authoritative across all four surfaces: one status
vocabulary + documented projections, one role→ACL table, and an explicit
`Issue`↔on-disk-Task mapping (the `provider: "native"` round-trip). Replace the
copy-pasted `dash/web/src/lib/board.ts` types with an import from a shared
package so dash and orgctl cannot drift.

### Repo hygiene

- **Committed build output (CLI tier):** `cli/orgctl/dist/` and `dist-test/`
  are tracked (24 files) with no umbrella `.gitignore` `dist` rule. The
  submodules (lens, dash) correctly ignore `dist`/`web/dist`. This asymmetry
  means the in-tree CLI re-commits generated JS on every build — the precise
  parallel-build clobber CLAUDE.md flags as the top lost-work cause. Current
  `git status` already carries 6 dirty `dist*` paths. **Fix: gitignore +
  `git rm --cached`.**
- **Untracked artifact dirs in the tree:** `web/dist/` exists on disk
  (untracked), plus `cli/orgctl/dist/{preflight.js,templates/,tools/}`. Noise
  that erodes the reliability of `git status` for teammates.
- **Submodule pointer drift:** `desktop/lens` is pinned to branch
  `wk5/stage1-now`; `desktop/dash` to `main`. Mixed-branch submodule pins are a
  reproducibility hazard for spawned teammates.
- **Root symlinks** `crawfish-dash`/`crawfish-lens` → `desktop/{dash,lens}` are
  untracked dev shims that resurrect pre-pivot paths. Harmless if no
  ownership/registry rule references them; dangerous if one does.
- **Single-source CSS holds:** `ui/tokens/globals.css` is genuinely the only
  `.css` file in the tree; all five consumers (web, lens, dash, platform) alias
  `@crawfish/ui`. **One exception:** dash's `vitest.config.ts` alias path
  (`../../ui`) does not match its `vite.config.ts` (`../../../ui`) — tests and
  build resolve different directories.

### Roadmap sequencing soundness

The numeric order (1→…→19, M3 parallel after Phase 7) is mostly defensible, but:

- **Sound:** M0 (1–3) before M1 (4–7) before M2 (8–11) holds; the board
  primitives in Phase 7 are correctly named the hard prerequisite for both
  M2 and M3. The org-contract already implements much of Phases 4–7
  (cycles, criteria, ACL, budget, FTS5, links) ahead of formal "Phase 1 of 19,
  0%" status in STATE.md — i.e., **code is ahead of the planning cursor**
  (NOW-W1/W2 work landed; STATE says Phase 1 not started). The roadmap cursor
  is stale relative to the tree.
- **Conflict — Phase 20 vs Phase 13 ordering of source-of-truth:** Phase 20
  (cloud `Issue`) is sequenced *ahead* of Phase 13 (on-disk intake) and
  declared the source of truth Phase 13 feeds. But the on-disk board substrate
  (Phase 7) and orchestrator foundation (Phase 12) are the substrate Phase 13
  needs. Phase 20 introduces a cloud `Issue` model with no reconciliation to
  the on-disk Task that Phase 7 produced — so the "source of truth" relationship
  is asserted before the bridge exists. Build the `Issue`↔Task mapping spec
  inside Phase 7/20, not deferred to Phase 13.
- **Blocker on the critical path:** ADR-002 gates all of M3. The roadmap lists
  it as Phase 12 SC#1 *while open*, so Phase 12 cannot start. M3 is effectively
  un-plannable today. The roadmap should mark M3 as "blocked on ADR-002"
  explicitly rather than "Not started."
- **ADR-001 assumed, not in ingest set:** the board data model is "assumed
  ratified" per STATE.md but the ADR doc is absent. Two boards (orgctl,
  projectctl) already cite "ADR-001 Option C" with different models — a sign
  the unwritten ADR is being interpreted divergently.

### Top 3 cross-cutting risks

1. **Board/Org/Issue model fragmentation (HIGH, structural).** Four board
   definitions, three status vocabularies, three member-role lexicons, two
   on-disk journals, one cloud Issue table — none reconciled by a shared type or
   contract spanning all surfaces. This is the seam every future phase (7, 13,
   20) crosses, and it is diverging by copy-paste today. Single highest-leverage
   fix: one authoritative cross-tier board/role contract + shared types.

2. **ADR-002 open → entire M3 un-plannable (BLOCKER).** The durable workflow
   engine choice gates Phases 12–19. No orchestrator skeleton exists. Until the
   ADR lands, M3 phases cannot be concretely planned and the 6 dependent O0
   open questions stay frozen.

3. **Committed `dist/` + mixed submodule branch + alias mismatch (HIGH,
   operational).** The CLI tier commits build output with no gitignore rule, the
   lens submodule is pinned to a feature branch, and dash test/build resolve
   different `@crawfish/ui` paths. Together these make the repo unsafe for the
   parallel agent-team fanouts the roadmap and CLAUDE.md plan for — exactly the
   clobber scenario the conventions exist to prevent.
