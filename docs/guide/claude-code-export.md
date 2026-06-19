# Exporting a Definition to Claude Code

`craw export --claude-code <definition>` turns a Crawfish **Definition** into a
[Claude Code](https://claude.com/claude-code) **subagent** — a Markdown file you can
drop into a project and run as a teammate. Optionally it also emits a **skill** so the
same Definition is invocable as a slash-command.

```bash
craw export --claude-code definitions/triage_fix
# → .claude/agents/triage-fix.md   (usable as a Claude Code subagent / teammate)

craw export --claude-code definitions/triage_fix --skill --dir .
# → .claude/agents/triage-fix.md
# → .claude/skills/triage-fix/SKILL.md
```

## What maps to what

A Crawfish Definition is an agent *team* authored as a directory; a Claude Code
subagent is a single Markdown file with YAML front-matter plus a system prompt. The
export composes them:

| Definition                                    | Claude Code subagent                        |
| --------------------------------------------- | ------------------------------------------- |
| `id` (the package name)                       | `name` (kebab-cased — CC requires it)       |
| lead/main agent's first prompt line           | `description` (when-to-use)                 |
| pinned model (`claude-opus-4-8`, …)           | `model` (`opus` / `sonnet` / `haiku`)       |
| `mock` / unpinned model                       | `model: inherit`                            |
| per-agent `tools` ∪ MCP tool names            | `tools` allowlist                           |
| MCP tool `<tool>` on server `<server>`        | `mcp__<server>__<tool>`                     |
| `instructions.md` + `agents/*.md` + injected  | the system-prompt body                      |

The lead (or `main`) agent's prompt leads the body; subagent prompts follow under
`## <role>` headings; any injected prompts are appended.

## The no-secrets guarantee

This is the security spine for the feature: **the generated file carries no secrets.**

A Definition never stores credentials inline — an `MCPConnection` references a secret by
*name* (`auth="GITHUB_TOKEN"`, an env-var reference resolved at run time). The export
maps tool and MCP *references* only: the `tools` allowlist names the exposed tools
(`mcp__github__create_issue`), never the `auth` reference and never a credential value.
The output is therefore safe to commit and share.

## Round-trip note

The mapping is symmetric in spirit: a Claude Code subagent author can drop a
`<name>.md` (front-matter + prompt) into a Crawfish Definition directory as
`instructions.md` (or an entry under `agents/`), and the compiler will pick up its
`model`/`tools`/`role` front-matter. Crawfish and Claude Code share the same authoring
substrate — front-matter over a Markdown prompt — so a team flows between them without a
rewrite.

See the [operations overview](operations.md) for the rest of the operate/integrate layer
and [SECURITY.md](../architecture/SECURITY.md) for the full spine.
