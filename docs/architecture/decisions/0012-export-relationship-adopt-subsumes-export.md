# ADR 0012 — `craw code adopt` subsumes `craw export --claude-code`

**Status:** Accepted · **Date:** 2026-06-25
**Affects:** `craw code adopt` / `craw code init` (UNFILED-ADOPT, CRA-245/279), the
`crawfish-*` plugin install, `craw export --claude-code` (`crawfish.ccexport`), the
`.claude/` tree layout
**Relates to:** RFC 0001 O-4 (the export relationship), `docs/guide/claude-code-export.md`,
`docs/architecture/SECURITY.md` ("operate and observe" — export carries no secrets), the
`.claude`-excluded-from-`sha` invariant (`docs/reference/definition.md` exclusion list)

---

## Context

Two features write into a project's `.claude/` tree, and RFC O-4 left their relationship
open:

* **`craw export --claude-code`** (`crawfish.ccexport.export_claude_code`) renders each
  Definition as a Claude Code **subagent** under `.claude/agents/<name>.md` (and, with
  `--skill`, `.claude/skills/<name>/SKILL.md`). It carries **no secrets** — it maps tool /
  MCP references only, never an `auth` reference or a credential value.
* **`craw code init` / `adopt`** install the **`crawfish-*` plugin bundle** (knowledge
  skills + command veneers) under `.claude/plugins/crawfish/` and start the `.crawfish/`
  ledger.

The open questions: does `adopt` re-implement export, call it, or ignore it? And do the two
`.claude/` writers collide? A naïve design — export writing `.claude/skills/<def>/` while
the plugin also ships `skills/` — would risk a name collision and, worse, could perturb a
Definition's content identity if any `.claude/` path leaked into the content sha.

## Decision

**`craw code adopt` subsumes `craw export --claude-code` as its export step**, and the two
`.claude/` namespaces are **disjoint** under a reserved `crawfish-*` prefix:

1. **Disjoint namespaces.** The plugin lives under `.claude/plugins/crawfish/` (every
   shipped component is `crawfish-*` / `craw-*`-prefixed per RFC O-4). Per-Definition
   exports live under `.claude/agents/<name>.md` (export's namespace). They never share a
   directory, so a per-Definition subagent can never collide with a plugin-shipped skill or
   command.

2. **`adopt` composes, never re-implements.** `adopt` calls `export_claude_code` directly
   for each discovered Definition (the export step), then reuses the already-built
   `craw code map` + `craw code sync` to validate the adopted tree. It adds **no new
   execution path** — the same machinery a human runs.

3. **Reconcile, never clobber.** `adopt` installs the plugin + ledger **only if absent**
   (the CRA-279 reconcile semantics), so adopting a project that was partially set up never
   resets its ledger or overwrites authored files.

4. **Identity is untouched.** The whole `.claude/` tree is already excluded from the
   Definition content sha (the exclusion list), so installing the plugin *and* writing
   per-Definition subagents both leave content identity byte-stable. Adoption never shifts a
   replay key.

`--no-export` opts out of step 2 (plugin + ledger + validation only).

## Consequences

* A single `craw code adopt` brings a pre-`craw code` project fully into the agent loop:
  plugin, ledger, per-Definition subagents, and a validation pass — without re-scaffolding.
* `craw export --claude-code` remains a standalone verb (a human may still run it directly);
  `adopt` is the orchestrated superset for the agent-loop onboarding case.
* The export invariant holds end to end: an adopted project's `.claude/agents/` files carry
  no secrets (`SECURITY.md` "operate and observe"), and the validation step re-runs the
  assembly gate via `sync`, so an adopted project with a fluid→sink wiring is flagged at
  adoption, not at first run.

## Rejected alternatives

* **`adopt` re-implements export.** Rejected: it would duplicate `crawfish.ccexport`'s
  rendering + the no-secrets invariant, risking drift between two emitters of the same file.
* **A single shared `.claude/` namespace.** Rejected: a per-Definition subagent named
  `triage` and a plugin skill could collide, and a shared tree muddies the reserved
  `crawfish-*` prefix that keeps plugin components identifiable.
* **`adopt` writes exports under `.claude/plugins/crawfish/agents/`.** Rejected: it would
  fold per-project, per-Definition output into the *bundle* namespace the plugin pin
  (UNFILED-PIN) digests, so a project's own exports would break the bundle's integrity hash.
