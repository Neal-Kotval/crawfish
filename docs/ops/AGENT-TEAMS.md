# Agent Teams — quick reference

Distilled from <https://code.claude.com/docs/en/agent-teams> + this repo's
`CLAUDE.md` ownership rules. Read this before spawning a team in Crawfish.

---

## What an agent team is

A **team lead** (the Claude Code session you start by running `claude`) spawns
**teammates** — separate Claude Code instances, each with its own context
window. Teammates coordinate through:

- a **shared task list** (claimable work items with dependencies)
- a **mailbox** (`SendMessage`-style direct teammate-to-teammate messages)
- automatic idle notifications back to the lead

Unlike subagents, teammates can talk to each other directly and you can step
into any teammate's session to give it instructions. The cost is significantly
more tokens (each teammate is a full Claude Code instance).

**When to use a team** — research/review, building independent modules,
debugging with competing hypotheses, cross-layer work where each layer can
be owned by a different teammate. Avoid for sequential work or same-file
edits.

---

## Prerequisites

- Claude Code v2.1.32 or later (`claude --version`)
- Experimental flag enabled. Either set in shell:
  ```bash
  export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
  ```
  or in `.claude/settings.json`:
  ```json
  { "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
  ```
- Optional but recommended for split panes: `tmux` (or iTerm2 with the `it2`
  CLI + Python API enabled). Otherwise teams run in-process.

---

## Display modes

| Mode         | How it looks                                         | How to set                                                  |
| ------------ | ---------------------------------------------------- | ----------------------------------------------------------- |
| `in-process` | All teammates in one terminal; `Shift+Down` to cycle | `--teammate-mode in-process` or `"teammateMode": "in-process"` |
| `tmux`       | Each teammate in its own pane                        | Default when inside a tmux session; or `"teammateMode": "tmux"` |
| `auto`       | tmux if inside tmux, else in-process                 | Default                                                     |

Toggle the task list with `Ctrl+T` (in-process). Press `Enter` to enter a
teammate's session, `Escape` to interrupt.

---

## How to start a team

You **do not** pre-author the team config file at
`~/.claude/teams/{team}/config.json` — Claude Code generates and rewrites it
automatically. To start a team, just tell the lead in natural language:

```text
Create an agent team for <task>. Spawn N teammates:
  - <name-A>: <role + ownership boundary>
  - <name-B>: …
Use <model> for each teammate.
[Optional] Require plan approval before any teammate writes code.
```

That's the whole API. The team md files we keep in this repo
(`docs/teams/*.md`) are **prompts you copy-paste** into the lead, not config
files Claude reads automatically.

### Reusable teammate roles via subagent definitions

You *can* pre-author teammate roles as subagents under `.claude/agents/<name>.md`
(project scope) or `~/.claude/agents/<name>.md` (user scope). Then spawn:

```text
Spawn a teammate using the <name> agent type to …
```

Caveats:
- The subagent body becomes *additional* system prompt, not a replacement.
- The subagent's `tools:` allowlist + `model:` apply.
- `skills:` and `mcpServers:` from the subagent frontmatter are **ignored**
  when run as a teammate — teammates use project/user settings.
- `SendMessage` + task tools are always available regardless of the `tools`
  allowlist.

---

## Controlling a running team

| You want…                            | Tell the lead…                                           |
| ------------------------------------ | -------------------------------------------------------- |
| Specific teammate count + model      | "Spawn 4 teammates using Sonnet…"                        |
| Force plan-mode before writing code  | "Require plan approval before they make any changes."    |
| Talk to one teammate                 | `Shift+Down` to cycle → type the message                 |
| Assign a specific task               | "Give task #3 to the `board-upgrade` teammate."          |
| Wait instead of doing work yourself  | "Wait for your teammates to complete their tasks."       |
| Shut a teammate down                 | "Ask the `flow-graph` teammate to shut down."            |
| Tear the whole team down             | "Clean up the team." (lead only — never from a teammate) |

Lead also auto-decides plan approval. To bias it: include criteria in the
spawn prompt ("only approve plans that include tests", etc.).

---

## Crawfish-specific rules

These are enforced by `CLAUDE.md` and must be in any team prompt for this
repo.

### Registry/aggregator files are lead-only

Two teammates editing these at once causes lost work. The lead serializes
edits to them at the end of the fan-out:

- `crawfish-lens/src/diagnoses/index.ts`
- `crawfish-lens/src/diagnoses/tool-optimizer-map.ts`
- `crawfish-lens/src/server/index.ts` (route registration)
- `crawfish-dash/web/src/App.tsx` (route table)
- `crawfish-app/src-tauri/tauri.conf.json`
- `ui/tokens/globals.css` (cross-cutting CSS — see `../product/DESIGN.md`)
- `ROADMAP.md`, `PRODUCT.md`, `docs/product/DESIGN.md`, `docs/product/BRAINSTORM.md`, `docs/product/INTEGRATIONS.md`
- Any `package.json` (dep bumps coordinate-only)
- Anything under `dist/` (generated)
- Shared schema files (e.g. `docs/specs/org-contract.md`)

A teammate that needs to edit one of these must `SendMessage` the lead first
and wait for an OK.

### Submodule = ownership boundary

The repo is five sibling submodules. Each teammate should get **exactly one
submodule path** (or one subdirectory inside one). Cross-cutting changes
(e.g. adding a new shared `cf-*` class consumed by both lens and dash) are
**lead-only** because two teammates each pulling the change locally would
race.

### Build serialization

- The lead runs `npx vite build` / `npx tsc -p …` — teammates do **not**.
- Teammates verify with type-check only: `npx tsc --noEmit -p tsconfig.json`
  in their assigned submodule.
- Nobody edits `dist/`.

### Worktrees for exploration

For "render the same thing three ways and pick a winner" tasks, spawn with
`isolation: "worktree"` so each teammate works in an isolated git worktree
(see `Agent` tool docs). The lead picks the winner; teammates' worktrees
that produce no changes are auto-cleaned.

---

## Hooks (optional quality gates)

These run in the lead session and apply to teammate events:

- `TeammateIdle` — exit 2 to push the teammate back with feedback instead of
  letting it idle (e.g. "type-check failed, fix and retry").
- `TaskCreated` — exit 2 to reject a task (e.g. block work that would touch
  a registry file).
- `TaskCompleted` — exit 2 to reject completion (e.g. require `tsc --noEmit`
  to pass before a task can be marked done).

Configure in `.claude/settings.json` under `"hooks"`.

---

## Known limitations

- **No resume**: `/resume` and `/rewind` don't restore in-process teammates.
- **Task status can lag** — sometimes a teammate forgets to mark done.
- **One team at a time** per lead. Clean up before starting a new one.
- **No nested teams** — teammates can't spawn teams.
- **Lead is fixed** for the lifetime of the team; can't transfer leadership.
- **Permissions inherited from lead** at spawn time; you can change per
  teammate after but not at spawn.

---

## Tear-down checklist

1. Confirm all assigned tasks are `completed` in the task list (`Ctrl+T`).
2. Ask each teammate to shut down: `"Ask <name> to shut down."`
3. From the lead: `"Clean up the team."`
4. If a tmux session lingers: `tmux ls` → `tmux kill-session -t <name>`.
