# Crawfish

> **The operating system for companies that run on AI agents.**

From solo founders spinning up their first agent team to enterprises managing hundreds of autonomous workers, Crawfish is the platform you build your org on. Pick a template — startup, dev shop, support team, research org — and get a preloaded set of agent containers with sensible defaults. Modify, extend, deploy.

See [PRODUCT.md](./PRODUCT.md) for the full pitch.

---

## Screenshots

### Home — create an org from a template

![Home](./docs/screenshots/home.png)

### Board — Jira-style kanban, shared between humans and agents

![Board](./docs/screenshots/org-board.png)

### Members — agents and humans as first-class peers

![Members](./docs/screenshots/org-members.png)

### Crons — scheduled manager runs

![Crons](./docs/screenshots/org-crons.png)

### Analytics — Dev signals from lens, Product signals from the board

![Analytics](./docs/screenshots/org-analytics.png)

### Files — hosted org filesystem all members can read/write

![Files](./docs/screenshots/org-files.png)

---

## Quick start

### Option A — desktop app (recommended)

```bash
git clone --recurse-submodules https://github.com/Neal-Kotval/crawfish.git
cd crawfish && npm run build
cd crawfish-app && cargo tauri build --bundles app
open src-tauri/target/release/bundle/macos/Crawfish.app
```

A native macOS window opens. Lens + dash are managed by the app; Quit (⌘Q) shuts everything down cleanly.

### Option B — terminal launcher

```bash
git clone --recurse-submodules https://github.com/Neal-Kotval/crawfish.git
cd crawfish && npm run build
node bin/crawfish.js
```

Boots **lens** (`:7878`) + **dash** (`:7880`) and opens the dashboard in your browser. `Ctrl-C` cleanly stops both.

Both options bind only to `127.0.0.1`. **Nothing leaves your machine.**

---

## What's inside

This is the umbrella repo. The code lives in six submodules:

| Submodule | What it is |
|---|---|
| **[crawfish-lens](./crawfish-lens)** | REST + SSE server. Owns the board, hosted FS, cron daemon, session analytics. Localhost `:7878`. |
| **[crawfish-dash](./crawfish-dash)** | The UI you see above. Org templates, members, board, files, analytics, crons. Localhost `:7880`. |
| **[crawfish-orgctl](./crawfish-orgctl)** | MCP server giving agents `board_*` and `org_fs_*` tools — so they can pick up tasks and read/write shared files. |
| **[crawfish-opt](./crawfish-opt)** | MCP server for semantic browser access (token-efficient `browser_*` tools). |
| **[crawfish-opt-codebase](./crawfish-opt-codebase)** | MCP server for semantic codebase navigation. **3.25× token reduction** on the bench vs. blind grep+Read. |
| **[crawfish-app](./crawfish-app)** | Tauri 2 desktop shell that wraps lens + dash as a native `.app`. |

The v1 architecture is pinned in [docs/specs/org-contract.md](./docs/specs/org-contract.md) — org.json schema, board event log, file-system rules, cron entries, MCP tool surface.

---

## Working in a submodule

Submodules are **independent git repos**. You commit and push from inside each submodule, then bump the umbrella's pointer:

```bash
cd crawfish-lens
# ... edits ...
git commit -am "..."
git push                       # to the submodule's own remote

cd ..
git add crawfish-lens
git commit -m "Bump crawfish-lens"
git push
```

The umbrella never contains submodule source — only a pinned commit hash per submodule. `crawfish-lens`, `crawfish-orgctl`, etc. each ship on their own cadence; the umbrella is a known-good combination.

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
├── PRODUCT.md                       # product pitch
├── ROADMAP.md                       # what shipped in v1, what's queued for v2
├── docs/
│   ├── specs/org-contract.md        # the binding v1 schema
│   └── screenshots/                 # the images above
├── crawfish-lens/                   # → github.com/Neal-Kotval/crawfish-lens
├── crawfish-dash/                   # → github.com/Neal-Kotval/crawfish-dash
├── crawfish-orgctl/                 # → github.com/Neal-Kotval/crawfish-orgctl
├── crawfish-opt/                    # → github.com/Neal-Kotval/crawfish-opt
├── crawfish-opt-codebase/           # → github.com/Neal-Kotval/crawfish-opt-codebase
└── crawfish-app/                    # → github.com/Neal-Kotval/crawfish-app
```

## License

MIT. See each submodule for its own LICENSE.
