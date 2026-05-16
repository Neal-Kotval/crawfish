# Phase 3 — spawn prompt

Paste the fenced block below into a fresh `claude` session at the repo root
(`/Users/nealkotval/crawfish`). Make sure:

1. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set (env or `.claude/settings.json`).
2. Claude Code ≥ v2.1.32 (`claude --version`).
3. You're on the branch you want the team to land its work on.
4. `git status` is clean (or at least, you know what's uncommitted).

The lead will do schema additions itself first, then fan out to five
teammates per `docs/teams/phase-3-native-ops.md`.

---

```text
You are the lead of an agent team for Phase 3 of the Crawfish roadmap.

READ FIRST, IN ORDER:
1. /Users/nealkotval/crawfish/AGENT-TEAMS.md  (how teams work + repo rules)
2. /Users/nealkotval/crawfish/CLAUDE.md       (ownership boundaries; binding)
3. /Users/nealkotval/crawfish/DESIGN.md       (UI rules; binding)
4. /Users/nealkotval/crawfish/ROADMAP.md      (read §Phase 3 in full)
5. /Users/nealkotval/crawfish/docs/teams/phase-3-native-ops.md  (the team spec)
6. /Users/nealkotval/crawfish/docs/specs/org-contract.md         (current schema)

GOAL
Ship Phase 3 of ROADMAP.md: native planning surface, board upgrades,
activity/comments/mentions, inter-agent flow graph, and governance
primitives v1. No external trackers, chat, or review tools.

BEFORE SPAWNING — you do this yourself, single commit:
Extend the CrawfishTask schema in docs/specs/org-contract.md and the
matching TypeScript types with the new fields: cycle_id, epic_id, links
(TaskLink[]), labels, watchers, activity_log (ActivityEntry[]). Also add
the TaskLink and ActivityEntry interfaces. Match the shape defined in
ROADMAP.md §"CrawfishTask — the universal work unit". Type-check both
crawfish-lens and crawfish-dash/web. Do not modify any registry files yet
beyond the schema doc.

THEN SPAWN A TEAM OF FIVE TEAMMATES, ALL SONNET 4.6:

  plan         — owns Plan tab + cycles/epics + FTS5 search.
                 Paths: crawfish-dash/web/src/routes/Plan.tsx (new),
                 crawfish-dash/web/src/lib/plan.ts (new),
                 crawfish-lens/src/server/cycles.ts (new),
                 crawfish-lens/src/server/search.ts (new),
                 crawfish-lens/test/fixtures/plan/.

  board        — owns Board tab upgrades + task drawer + task card.
                 Paths: crawfish-dash/web/src/routes/Board.tsx,
                 crawfish-dash/web/src/lib/board.ts,
                 crawfish-dash/web/src/components/TaskDrawer.tsx (new),
                 crawfish-dash/web/src/components/TaskCard.tsx (new).

  activity     — owns activity feed + comments + mentions + MCP tools.
                 REQUIRE PLAN APPROVAL FROM ME before any code edits.
                 Paths: crawfish-dash/web/src/components/ActivityFeed.tsx (new),
                 crawfish-dash/web/src/components/Comments.tsx (new),
                 crawfish-dash/web/src/lib/activity.ts (new),
                 crawfish-lens/src/server/activity.ts (new),
                 crawfish-orgctl/src/tools/activity.ts (new).

  flow-graph   — owns Analytics Flow sub-tab + D3 graph + lens aggregation.
                 Paths: crawfish-dash/web/src/routes/Analytics.tsx (extend),
                 crawfish-dash/web/src/components/FlowGraph.tsx (new),
                 crawfish-lens/src/server/flow.ts (new).

  governance   — owns policy enforcement + audit log + policies UI.
                 REQUIRE PLAN APPROVAL FROM ME before any code edits.
                 Paths: crawfish-lens/src/server/policy.ts (new),
                 crawfish-lens/src/server/audit.ts (new),
                 crawfish-dash/web/src/routes/policies.tsx (extend existing),
                 crawfish-dash/web/src/components/PolicyEditor.tsx (new).

ENFORCE FOR ALL FIVE
- Registry files are lead-only. Per CLAUDE.md, NEVER let a teammate edit
  any of: crawfish-lens/src/server/index.ts, crawfish-dash/web/src/App.tsx,
  crawfish-orgctl/src/tools.ts, ui/tokens/globals.css, package.json,
  any *.md at repo root, or anything in dist/. If a teammate hits one of
  these, they MUST SendMessage you and wait.
- Teammates DO NOT run builds. They verify via `npx tsc --noEmit -p
  tsconfig.json` in their assigned submodule. Only you run `npx vite
  build` or full builds.
- A teammate's task is not done until its files type-check AND no file
  outside its ownership column was modified. Reject task completion that
  violates either.
- UI work must use the shared design system (DESIGN.md): no inline styles
  for color/spacing/typography. New shared classes go in ui/tokens/
  globals.css — request via SendMessage to you; you write them.

COORDINATION
- Spawn all five at once with descriptive names matching the list above.
- Tell each teammate explicitly which files they own and which they must
  not touch (copy from docs/teams/phase-3-native-ops.md "Ownership matrix").
- Plan + Board first (UI-visible). Activity ships its components and
  Board consumes them via SendMessage handshake. Flow graph and
  governance run fully independent.
- Wait for teammates instead of doing their work yourself. If you find
  yourself about to write code in a teammate's column, stop and message
  the teammate instead.
- Pre-approve plans only if they include type-check evidence and respect
  the ownership matrix. Reject plans that touch registry files or use
  inline styles.

WHEN ALL FIVE ARE DONE
Do the lead finalization pass:
1. Register new routes in crawfish-lens/src/server/index.ts
   (/api/cycles, /api/search, /api/flow, /api/policy, /api/audit).
2. Register new MCP tools in crawfish-orgctl/src/tools.ts.
3. Add /plan to crawfish-dash/web/src/App.tsx.
4. Run a full build of crawfish-dash and crawfish-lens; fix any glue gaps.
5. End-to-end demo run: create a cycle, add tasks with epic + links,
   trigger budget breach, watch flow graph populate. Capture a one-page
   wrap-up at docs/teams/phase-3-notes.md describing what shipped and
   what was deferred.
6. Shut down each teammate, then run cleanup.

Confirm you've read all six files above, summarize the plan in five
bullets, then do the schema additions and spawn the team. Do not skip
the read step.
```

---

## After paste — first sanity checks

When the lead is up:

- Type `Ctrl+T` to confirm the task list is empty until it spawns.
- After spawn, `Shift+Down` to cycle through teammates and confirm each
  one read its ownership column.
- If the lead starts writing code in a teammate's column: send it
  `"Wait for your teammates. Don't do their work."`
- If a teammate edits a registry file by mistake: revert via git, message
  the teammate with the rule, and let the lead re-serialize.

## Tear-down

When done (see lead's wrap-up note):

```text
Ask each teammate to shut down. Then clean up the team.
```

Then `tmux ls` to verify no orphan sessions; `tmux kill-session -t <name>`
if any linger.
