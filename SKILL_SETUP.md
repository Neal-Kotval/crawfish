# Skill & plugin setup — manual steps

Everything below requires *your* input (brand info, interactive Q&A) or a Claude Code restart. Work through it in order.

---

## 0. Restart Claude Code

Plugin-provided slash commands and MCP servers only register on launch. In your terminal:

```
exit
claude
```

Then verify with `/help` — you should see commands from `superpowers`, `contextmode`, `mem`, `gsd-*`, `skill-creator`, and Playwright tools under `/mcp`.

---

## 1. Sanity-check the new stack

Run each and confirm no error:

```
/mem:stats                   # claude-mem worker on port 37777
/contextmode:ctx-stats       # context-mode interception stats
/gsd-help                    # GSD command index
```

Quick MCP check:

> use playwright mcp to open https://example.com and take a screenshot

---

## 2. Impeccable — one-time brand teach

Impeccable's taste defaults are generic until you give it your brand context. Run once per project (writes `.impeccable.md` in cwd):

```
/teach-impeccable
```

It will ask about: product, audience, voice, visual references, anti-patterns to avoid, palette, type system. Answer as specifically as you can — vague answers produce vague output.

Re-run when product positioning shifts.

---

## 3. Huashu-design — personal asset index (optional)

Only needed if you want huashu-design to know your brand assets when generating prototypes/decks. Create `~/.claude/memory/personal-asset-index.json` with:

```json
{
  "brand": {
    "name": "Crawfish",
    "logo_paths": ["/abs/path/to/logo.svg"],
    "palette": {
      "primary": "#xxxxxx",
      "accent":  "#xxxxxx",
      "bg":      "#xxxxxx",
      "fg":      "#xxxxxx"
    },
    "typography": {
      "display": "Font Name",
      "body":    "Font Name",
      "mono":    "Font Name"
    }
  },
  "references": {
    "inspiration_urls": [],
    "screenshot_paths": []
  },
  "voice": {
    "tone": "e.g. terse, technical, anti-corporate",
    "avoid": ["buzzwords", "exclamation points"]
  }
}
```

The dir already exists — just drop the file in.

---

## 4. UI/UX Pro Max — verify Python

Python 3.14.3 is installed, so the search scripts will work out of the box. Nothing to do.

---

## 5. GSD — opt-in hooks audit

GSD installed several hooks into your global `~/.claude/settings.json`:

- update check
- context window monitor
- prompt injection guard
- read-before-edit guard
- read injection scanner
- workflow guard (opt-in)
- commit validation (opt-in)
- session state orientation (opt-in)
- phase boundary detection (opt-in)

If any feel intrusive after a few sessions, disable them via:

```
/gsd-config
```

The opt-in ones are off by default.

---

## 6. Optional: tighten permissions

After a couple of sessions, run:

```
/fewer-permission-prompts
```

It scans your transcripts and auto-allowlists common safe read-only commands to cut down on permission prompts.

---

## 7. Skill routing — already configured

`CLAUDE.md` in this repo has a "Skill auto-routing" section. I'll reach for the right skill automatically based on the situation; you don't need to type slash commands yourself unless you want to force a specific one.

If I pick the wrong skill for a task, tell me and I'll tighten the rule in `CLAUDE.md`.

---

## Reference — what got installed

**Plugins (user scope):**
- `frontend-design`, `skill-creator`, `playwright`, `superpowers` (anthropic official)
- `context-mode` (mksglu/claude-context-mode)
- `claude-mem` (thedotmack/claude-mem)
- `ui-ux-pro-max` (nextlevelbuilder/ui-ux-pro-max-skill)

**Skills via `npx skills add` → `./.agents/skills/` (project scope, symlinked):**
- `impeccable` + 13 taste siblings (pbakaus/impeccable)
- Taste skill bundle (Leonxlnx/taste-skill): gpt-taste, design-taste-frontend, high-end-visual-design, minimalist-ui, industrial-brutalist-ui, redesign-existing-projects, stitch-design-taste, brandkit, image-to-code, imagegen-frontend-{web,mobile}, full-output-enforcement
- `huashu-design` (alchaincyf/huashu-design)

**GSD (global, ~/.claude/skills/):** 67 skills, `/gsd-*` prefix.
