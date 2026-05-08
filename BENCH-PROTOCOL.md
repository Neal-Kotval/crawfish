# Bench protocol — vanilla vs. optimized on this repo

Two-run comparison. Same project (`/Users/nealkotval/crawfish`), same prompts (`bench/prompts.md`), only difference is whether `crawfish-codebase` MCP is installed.

## Pre-flight

Both lens and dash should be running:

```bash
node ~/crawfish/bin/crawfish.js
```

Open dash at <http://127.0.0.1:7880>. Keep it open in another window — you'll watch sessions populate live.

Confirm the prompts file is reachable from the Claude Code working dir:

```bash
ls ~/crawfish/bench/prompts.md
```

## Run A — vanilla baseline (no crawfish optimizers)

### Snapshot + uninstall

```bash
# Snapshot current MCP state in case anything is already there
cp ~/.claude/settings.json ~/.claude/settings.json.bench-snapshot

# Remove crawfish-codebase if it's installed
claude mcp remove crawfish-codebase 2>/dev/null || true
claude mcp remove crawfish 2>/dev/null || true

# Sanity check — should NOT list any crawfish-* servers
claude mcp list 2>&1 | grep -i crawfish || echo "✓ no crawfish MCPs installed"
```

### Run

```bash
cd ~/crawfish
claude
```

In the Claude Code prompt:

1. `cat bench/prompts.md` to refresh the prompt list.
2. Paste **Prompt 1** verbatim. Wait for completion (subagents finish, parent returns a summary).
3. Paste **Prompt 2**. Wait.
4. Paste **Prompt 3**. Wait.
5. Type `/exit` or close the terminal window.

### Capture session id

```bash
# The most recently modified jsonl in the project's transcript dir is your run
ls -t ~/.claude/projects/-Users-nealkotval-crawfish/*.jsonl | head -1
# Note the basename (UUID) — that's your "Vanilla" session id.
```

Or just open dash → **Sessions** tab; the top card with mtime "just now" is yours.

## Run B — optimized (crawfish-codebase installed)

### Build + install

```bash
cd ~/crawfish/crawfish-opt-codebase
npm run build

# `-s user` puts it in user scope so it's available regardless of cwd.
# (Default scope is "local" — tied to the directory you run `claude` from.)
# `--` separates Claude's flags from the stdio-server command + args.
claude mcp add -s user crawfish-codebase -- node "$(pwd)/dist/index.js"

# Confirm — should show "✓ Connected"
claude mcp list | grep crawfish-codebase
```

### Run

```bash
cd ~/crawfish
claude
```

Same three prompts in the same order. **Don't deviate** — the comparison's value depends on prompt parity.

### Capture session id

Same as before. Note this UUID as your "+ crawfish-codebase" session.

## Compare

Open dash → **Compare** tab.

- Side A picker → pick the **Vanilla** session UUID. Rename label to `Vanilla`.
- Side B picker → pick the **+ crawfish-codebase** session UUID. Rename label to `+ crawfish-codebase`.

The view renders a headline delta, per-side panels (turns / cache hit / subagent count), and a per-tool delta table sorted by absolute byte difference.

## Cleanup

```bash
# Restore original settings.json
cp ~/.claude/settings.json.bench-snapshot ~/.claude/settings.json

# Or just remove crawfish-codebase (note: `-s user` matches the install scope)
claude mcp remove -s user crawfish-codebase
```

## Honest caveats

- **Non-determinism.** Even with identical prompts, the model's tool-call order and subagent prompts differ slightly between runs. The comparison is directional, not within-1%.
- **Cache cost dominates totals.** A 996-turn session pays mostly for cached reads of the prompt prefix. The optimizer shrinks tool results but doesn't change the prompt backbone — so % savings on `totalTokens` is in the single digits even when per-tool byte deltas are >50%.
- **The headline number to demo.** It's the per-tool `Read` and `Bash` byte deltas, not session totals. Those are the lines that show "the optimizer redirected the agent to a smaller tool result on N out of M calls."
- **Subagent counts should match.** If they don't, the prompts produced different fan-out plans — repeat the run that fanned-out less.

## Naming convention

Save the two session UUIDs and a short summary in `bench/runs.md` as you go. Example:

```markdown
## 2026-05-08 — round 1

- Vanilla:                ef74e3e6-…  →  157M tokens, 996 turns, 5 subagents
- + crawfish-codebase:    abc12345-…  →  82M tokens,  812 turns, 5 subagents
- Verdict: −47% total, Read bytes −67%, Bash bytes −41%
```

Future rounds (after we ship more optimizers) compare the same vanilla baseline against richer variants: `+ crawfish-codebase + crawfish-opt-logs`, etc.
