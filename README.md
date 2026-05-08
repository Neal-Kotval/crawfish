# Crawfish

> **The token observability layer for Claude Code, plus a family of MCP optimizers built around it.**

This is the umbrella repo. The actual code lives in two submodules:

| Submodule | What it is | Status |
|---|---|---|
| **[crawfish-opt](./crawfish-opt)** | Optimizer line — MCP server for the browser/DOM token sink. | v0.2 |
| **[crawfish-opt-codebase](./crawfish-opt-codebase)** | Optimizer line — MCP server for codebase navigation (replaces blind grep+Read chains; **3.25× token reduction** on the bench). | v0.1 |
| **[crawfish-lens](./crawfish-lens)** | Local observability — reads `~/.claude/projects` JSONL transcripts, surfaces diagnoses, links to optimizers. Localhost dashboard at `:7878`. | M1 shipped |
| **[crawfish-dash](./crawfish-dash)** | The umbrella UI. Three tabs (Agents / Optimizers / Sessions) over a localhost web server. CRUD for `~/.claude/agents/`, live-proxies lens for sessions, marketplace for one-click-copy install commands. | v0.1 (webapp) |

For the full product story, see [crawfish-lens/PRODUCT.md](./crawfish-lens/PRODUCT.md). For why these are separate repos, see [crawfish-lens/docs/relationship-to-crawfish.md](./crawfish-lens/docs/relationship-to-crawfish.md).

## Cloning

```bash
git clone --recurse-submodules https://github.com/Neal-Kotval/crawfish.git
# or, after a plain clone:
git submodule update --init --recursive
```

## Working in a submodule

Submodules are **independent git repos**. You commit and push from inside each submodule, then bump the umbrella's pointer:

```bash
# Edit code in a submodule
cd crawfish-opt
# ... edits ...
git commit -am "..."
git push                       # to the submodule's own remote

# Back in the umbrella, record the new submodule SHA
cd ..
git add crawfish-opt
git commit -m "Bump crawfish-opt"
git push
```

The umbrella never contains submodule source — only a pinned commit hash per submodule. That's the whole point: `crawfish-opt` and `crawfish-lens` ship on their own cadence; the umbrella is a known-good combination.

## Updating to latest

```bash
git submodule update --remote                # fetch each submodule's tracked branch
git submodule update --remote crawfish-lens  # just one
```

## Layout

```
crawfish/                            # this umbrella repo
├── .gitmodules                      # submodule pointers
├── README.md                        # you are here
├── ROADMAP.md                       # multi-phase plan, P0 → P5
├── crawfish-opt/                    # → github.com/Neal-Kotval/crawfish-opt
├── crawfish-opt-codebase/           # → github.com/Neal-Kotval/crawfish-opt-codebase
├── crawfish-lens/                   # → github.com/Neal-Kotval/crawfish-lens
└── crawfish-dash/                   # → github.com/Neal-Kotval/crawfish-dash
```

## Running the platform

```bash
# terminal 1 — the observability engine
cd crawfish-lens && npm install && npm run build && npm run serve   # → :7878

# terminal 2 — the umbrella UI
cd crawfish-dash && npm install && npm run build && npm run serve   # → :7880
```

Open dash at <http://127.0.0.1:7880> for the polished surface; lens at <http://127.0.0.1:7878> for the deep-dive token detail.

## License

MIT. See each submodule for its own LICENSE.
