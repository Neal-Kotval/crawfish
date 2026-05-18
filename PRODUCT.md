# Crawfish — repo map

**The operating system for companies that run on AI agents.** Pick a template — startup, dev shop, support team, research org — and get a preloaded set of agent containers with sensible defaults. Run it locally, sign in to share. This file is the orientation map for the codebase; for the elevator pitch see `README.md`, for what's shipping next see `ROADMAP.md`, for the long-range vision see `docs/roadmap/GRAND_PLAN.md`.

---

## Top-level layout

```
crawfish/
├── crawfish-lens/         (submodule) JSONL transcript reader + REST/SSE API + 8 diagnoses rules
├── crawfish-dash/         (submodule) Local dashboard UI (Tauri-hosted) — sessions, agents, board, analytics
├── crawfish-app/          (submodule) Tauri shell that boots lens + dash as children
├── crawfish-opt/          (submodule) Browser-side token optimizer (MCP server)
├── crawfish-opt-codebase/ (submodule) Codebase token optimizer — 3.25× reduction on bench
├── crawfish-platform/     Signed-in web SPA — Clerk auth, org/project import, dashboard tabs
├── crawfish-server/       Platform backend — Express + Prisma + Clerk session verification
├── crawfish-orgctl/       Org-control MCP server — board + hosted-FS tools at ~/.crawfish/orgs/<id>/
├── crawfish-projectctl/   Per-project .crawfish/ engine — CLI + MCP + hooks preset
├── crawfish-web/          Marketing & onboarding site for crawfish.dev
├── crawfish-starter-app/  Tiny Express target repo for the MVP demo
├── bin/                   Umbrella launchers: `crawfish` (boots lens+dash), `craw` (per-project verbs)
├── e2e/                   Cross-surface Playwright suite
├── ui/                    Shared design tokens — globals.css consumed by platform + dash via @crawfish/ui
├── docs/                  Documentation (see docs/README.md)
├── scripts/               Repo-wide tooling — dev.sh, run-bench.sh, build-dmg.sh, smoke-15min.ts
├── bench/                 Benchmark fixtures + prompts
├── dev.sh / build-app.sh  Top-level entry scripts
├── package.json           Umbrella — builds lens + dash, exposes `crawfish` / `craw` bins
├── ROADMAP.md             Build schedule — start here for what's shipping
├── CLAUDE.md              Project instructions loaded by every Claude Code session
├── README.md              GitHub front page
└── PRODUCT.md             This file
```

Five `crawfish-*` directories are git submodules (their paths are pinned by `.gitmodules`). The rest are in-tree packages or supporting folders.

---

## The product, in three layers

### CLI layer

- **`crawfish-orgctl`** — MCP server giving agents `board_*` and `org_fs_*` tools against `~/.crawfish/orgs/<id>/`. Contract: `docs/specs/org-contract.md`.
- **`crawfish-projectctl`** — manages `.crawfish/` inside a user's repo (memory, context, decisions, activity). Contract: `docs/superpowers/specs/2026-05-18-crawfish-project-folder-design.md`.
- **`bin/craw`** — shim that dispatches per-project verbs (`craw init`, `craw status`, etc.) to `crawfish-projectctl`.
- **`bin/crawfish`** — umbrella launcher that boots `crawfish-lens` and `crawfish-dash` together (or via the Tauri shell).

### Local runtime

- **`crawfish-lens`** — Node service. Reads Claude Code JSONL sessions, exposes REST + SSE, runs the diagnoses engine. The local data plane.
- **`crawfish-dash`** — React UI inside Tauri. Sessions / Agents / Plan / Board / Compare / Settings / Analytics tabs. Proxies to lens.
- **`crawfish-app`** — Tauri shell. Spawns lens + dash as children, owns the desktop window. How to start: `docs/ops/RUNNING.md`.

### Cloud / web

- **`crawfish-platform`** — signed-in React SPA at `:5174`. Clerk-based auth, org canvas, repo import, GitHub-hosted file rendering for the 5-tab project dashboard.
- **`crawfish-server`** — Express backend on Prisma + SQLite (dev) / Postgres (prod). Verifies Clerk sessions, stores `Organization` / `Project` / `Member` rows, brokers GitHub OAuth handoff. Auth + import contract: `docs/superpowers/specs/2026-05-18-github-login-import-design.md`.
- **`crawfish-web`** — marketing site (crawfish.dev). Warm-paper + vermillion brand from `docs/product/DESIGN.md`.

---

## How a user's repo gets "Crawfish-shaped"

User signs in to the web platform with GitHub via Clerk. They create an Organization, then import one of their GitHub repos — the server records a `Project` bookmark linked to the repo URL. On the paired local dashboard, they click **Clone**: `crawfish-dash` runs `git clone` and then `craw init` (via `crawfish-projectctl`), which scaffolds `.crawfish/` inside the repo (memory.md, context.md, roadmap.md, decisions.md, activity.md). Pushed to GitHub, the platform dashboard reads those five files from the GitHub raw API and renders them as five tabs — Memory / Context / Roadmap / Decisions / Activity. The repo is now legible to every agent the user hires.

---

## Where to find the contracts

- **Auth + repo import:** `docs/superpowers/specs/2026-05-18-github-login-import-design.md`
- **Per-project `.crawfish/` format:** `docs/superpowers/specs/2026-05-18-crawfish-project-folder-design.md`
- **Org filesystem + MCP tools:** `docs/specs/org-contract.md`
- **Preflight (dependency / port checks):** `docs/specs/preflight-contract.md`
- **Phase 4 architecture:** `docs/specs/p4-architecture.md`
- **Active build schedule:** `ROADMAP.md`
- **Long-range vision:** `docs/roadmap/GRAND_PLAN.md`
- **Design system:** `docs/product/DESIGN.md` + `ui/tokens/globals.css`
- **Runtime adapter matrix:** `docs/product/INTEGRATIONS.md`

---

## What to read next

- … a backend engineer → `crawfish-server/` (Express routes, Prisma schema at `crawfish-server/prisma/schema.prisma`).
- … a frontend engineer on the web app → `crawfish-platform/src/pages/` + `ui/tokens/globals.css`.
- … working on the per-project CLI → `crawfish-projectctl/` + its spec under `docs/superpowers/specs/`.
- … exploring the local Tauri app → `crawfish-app/` + `crawfish-dash/`, then `docs/ops/RUNNING.md`.
- … contributing diagnoses rules → `crawfish-lens/src/diagnoses/` (note `CLAUDE.md` ownership rules — registry edits are lead-only).
- … running the bench → `docs/ops/BENCH-PROTOCOL.md` + `scripts/run-bench.sh`.
- … spawning an agent team → `docs/ops/AGENT-TEAMS.md` + `CLAUDE.md`.
