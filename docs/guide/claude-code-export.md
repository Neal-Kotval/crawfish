# Export a Definition to Claude Code

`craw export --claude-code <definition>` turns a Crawfish *Definition* (a directory of
agent prompts and config) into a [Claude Code](https://claude.com/claude-code) *subagent*:
a Markdown file you drop into a project and run as a teammate. Add `--skill` and it also
emits a *skill*, so you can invoke the same Definition as a slash command.

```bash
craw export --claude-code definitions/triage_fix
# → .claude/agents/triage-fix.md   (usable as a Claude Code subagent / teammate)

craw export --claude-code definitions/triage_fix --skill --dir .
# → .claude/agents/triage-fix.md
# → .claude/skills/triage-fix/SKILL.md
```

## What maps to what

The export folds an agent team into a single file. A Crawfish Definition is a directory; a
Claude Code subagent is one Markdown file, with YAML front-matter over a system prompt:

| Definition                                    | Claude Code subagent                        |
| --------------------------------------------- | ------------------------------------------- |
| `id` (the package name)                       | `name` (kebab-cased, which CC requires)     |
| lead/main agent's first prompt line           | `description` (when to use)                 |
| pinned model (`claude-opus-4-8`, …)           | `model` (`opus` / `sonnet` / `haiku`)       |
| `mock` or unpinned model                      | `model: inherit`                            |
| per-agent `tools` ∪ MCP tool names            | `tools` allowlist                           |
| MCP tool `<tool>` on server `<server>`        | `mcp__<server>__<tool>`                     |
| `instructions.md` + `agents/*.md` + injected  | the system-prompt body                      |

The lead (or `main`) agent's prompt leads the body. Subagent prompts follow under
`## <role>` headings. Any injected prompts are appended at the end.

## Why the output carries no secrets

The generated file carries no secrets. A Definition never stores credentials inline. An
`MCPConnection` references a secret by name. `auth="GITHUB_TOKEN"` is an env-var reference
resolved at run time. The export maps references only. The `tools` allowlist names the
exposed tools, such as `mcp__github__create_issue`, but never the `auth` reference and
never a credential value.

!!! warning "The export never emits a secret"
    The exported file holds tool names and env-var references, never a credential value. So
    the output is safe to commit and share. The secret resolves at run time, from the
    environment.

## Round-trip from Claude Code back to a Definition

The mapping runs both ways. Drop a Claude Code subagent's `<name>.md` (front-matter plus
prompt) into a Crawfish Definition directory as `instructions.md`, or as an entry under
`agents/`, and the compiler picks up its `model`, `tools`, and `role` front-matter. Both
tools author agents the same way, front-matter over a Markdown prompt, so a team moves
between them without a rewrite.

## Adopting an existing project (`craw code adopt`)

`craw code adopt` brings a pre-`craw code` project into the agent loop in one step: it
installs the `crawfish-*` plugin and the `.crawfish/` ledger (reconcile-only, never
clobbering authored files), **runs this export for each Definition**, then validates the
tree with `craw code map` + `craw code sync`. Adopt *subsumes* `craw export --claude-code`
as its export step, with **disjoint `.claude/` namespaces** — the plugin lives under
`.claude/plugins/crawfish/`, the per-Definition subagents under `.claude/agents/`. Both are
excluded from the Definition content sha, so adoption never shifts a replay key. See
[ADR 0012](../architecture/decisions/0012-export-relationship-adopt-subsumes-export.md) for
the rationale and the rejected alternatives.

## Next steps

- [Run a pipeline in the background](operations.md) covers the rest of the operate layer.
- [SECURITY.md](../architecture/SECURITY.md) covers the full set of invariants.
