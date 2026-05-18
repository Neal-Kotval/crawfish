# crawfish-projectctl

The per-project `.crawfish/` folder engine for Crawfish.

See the design spec: `docs/superpowers/specs/2026-05-18-crawfish-project-folder-design.md`.

## CLI

```
crawfish-projectctl init                    # scaffold .crawfish/
crawfish-projectctl refresh [files...]      # re-derive *.md from sources
crawfish-projectctl status                  # which files are stale?
crawfish-projectctl doctor                  # validate schema + sources
crawfish-projectctl decision add <t> <b>    # append an ADR entry
crawfish-projectctl activity record [s]     # append a session summary
crawfish-projectctl memory append <text>    # append a deduped memory entry
crawfish-projectctl install-hooks           # write three hook entries to .claude/settings.json
crawfish-projectctl uninstall-hooks         # remove them
```

## MCP

Run `crawfish-projectctl-mcp` over stdio. Tools:
- `project_init`, `project_refresh`, `project_status`, `project_decision_add`, `project_memory_append`, `project_read`.

## Hooks

`install-hooks` writes:
- `SessionEnd` → `crawfish-projectctl activity record`
- `PostToolUse` (Edit|Write) → `crawfish-projectctl refresh --debounce 30000`
- `UserPromptSubmit` → `crawfish-projectctl refresh memory.md`

Each entry is tagged with `_crawfish: true` so uninstall removes only its own hooks.
