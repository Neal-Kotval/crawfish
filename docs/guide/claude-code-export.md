# Exporting a Definition to Claude Code

`craw export --claude-code <definition>` turns a Crawfish **Definition** into a
[Claude Code](https://claude.com/claude-code) **subagent**: a Markdown file you drop
into a project and run as a teammate. Add `--skill` and it also emits a **skill**, so
you can invoke the same Definition as a slash-command.

```bash
craw export --claude-code definitions/triage_fix
# → .claude/agents/triage-fix.md   (usable as a Claude Code subagent / teammate)

craw export --claude-code definitions/triage_fix --skill --dir .
# → .claude/agents/triage-fix.md
# → .claude/skills/triage-fix/SKILL.md
```

## What maps to what

The export folds an agent *team* into a single file. A Crawfish Definition is a
directory; a Claude Code subagent is one Markdown file — YAML front-matter plus a
system prompt:

| Definition                                    | Claude Code subagent                        |
| --------------------------------------------- | ------------------------------------------- |
| `id` (the package name)                       | `name` (kebab-cased — CC requires it)       |
| lead/main agent's first prompt line           | `description` (when-to-use)                 |
| pinned model (`claude-opus-4-8`, …)           | `model` (`opus` / `sonnet` / `haiku`)       |
| `mock` / unpinned model                       | `model: inherit`                            |
| per-agent `tools` ∪ MCP tool names            | `tools` allowlist                           |
| MCP tool `<tool>` on server `<server>`        | `mcp__<server>__<tool>`                     |
| `instructions.md` + `agents/*.md` + injected  | the system-prompt body                      |

The lead (or `main`) agent's prompt leads the body. Subagent prompts follow under
`## <role>` headings. Any injected prompts are appended at the end.

## No secrets in the output

The generated file carries no secrets. A Definition never stores credentials inline. An
`MCPConnection` references a secret by *name* — `auth="GITHUB_TOKEN"` is an env-var
reference resolved at run time. The export maps references only. The `tools` allowlist
names the exposed tools, such as `mcp__github__create_issue`, but never the `auth`
reference and never a credential value.

!!! warning "The export never emits a secret"
    The exported file holds tool names and env-var *references*, never a credential
    value. So the output is safe to commit and share. The secret resolves at run time,
    from the environment.

## Round-trip note

The mapping runs both ways. Drop a Claude Code subagent's `<name>.md` (front-matter
plus prompt) into a Crawfish Definition directory as `instructions.md`, or as an entry
under `agents/`, and the compiler picks up its `model`, `tools`, and `role`
front-matter. Both tools author agents the same way — front-matter over a Markdown
prompt — so a team moves between them without a rewrite.

## See also

- [Operations overview](operations.md) — the rest of the operate/integrate layer.
- [Security spine](../architecture/SECURITY.md) — the full set of invariants.
