# Build instructions

How to build and run every package in this umbrella. Layout recap:

```
crawfish/
├── ui/                  # shared design tokens (CSS only, no build)
├── cloud/
│   ├── platform/        # signed-in web SPA (Vite + React + Clerk)
│   └── server/          # Express + Prisma backend
├── desktop/
│   ├── dash/            # local dashboard (Node server + Vite SPA)
│   ├── lens/            # transcript reader (Node server + Vite SPA)
│   └── opt*/            # MCP optimizer servers
├── cli/
│   ├── projectctl/      # per-project `.crawfish/` engine
│   └── orgctl/          # org-control MCP server
├── web/                 # marketing site (Vite)
└── bin/
    ├── craw.js          # shorthand → dispatches to cli/projectctl
    └── crawfish.js
```

## Prereqs

- Node ≥ 20 (`node -v`)
- npm
- For `cloud/server`: a Postgres URL in `cloud/server/.env`
  (`DATABASE_URL=...`) — required for `prisma generate` during build.

## First-time setup

Install deps in every submodule. From the umbrella root:

```bash
for d in ui cloud/platform cloud/server desktop/dash desktop/lens \
         cli/projectctl cli/orgctl web; do
  (cd "$d" && npm install)
done
```

## Building everything (in order — don't run in parallel)

CLAUDE.md rule: never run two `tsc`/`vite build` invocations concurrently in
the same submodule tree — they share `dist/` and clobber each other.

```bash
# 1. CLI
( cd cli/projectctl && npm run build )
( cd cli/orgctl     && npm run build )

# 2. Backend
( cd cloud/server   && npm run build )

# 3. Frontends
( cd cloud/platform && npm run build )
( cd desktop/dash   && npm run build )   # builds server then web
( cd desktop/lens   && npm run build:server )   # see "Known issues"
( cd web            && npx vite build )         # see "Known issues"
```

## Per-package details

### `cli/projectctl` — `craw init` and friends

```bash
cd cli/projectctl
npm run build       # → dist/index.js, dist/mcp/server.js
npm test            # 33 tests
```

Outputs two binaries (via `package.json#bin`):

- `crawfish-projectctl` — main CLI
- `crawfish-projectctl-mcp` — MCP server for Claude Code etc.

The umbrella ships a `craw` shim at `bin/craw.js` that dispatches to
projectctl's `dist/index.js`. Once projectctl is built, `craw` works
without npm-publishing.

#### Putting `craw` on your PATH

The repo doesn't auto-install `craw` anywhere. Pick one:

```bash
# Option A — symlink to a user-writable PATH dir (no sudo)
chmod +x bin/craw.js
ln -sf "$PWD/bin/craw.js" ~/.local/bin/craw

# Option B — shell alias
alias craw="node $PWD/bin/craw.js"

# Option C — direct invocation, no install
node /Users/nealkotval/crawfish/bin/craw.js init
```

Verify:

```bash
craw --help    # prints the verb table
```

### `cli/orgctl` — org-control MCP server

```bash
cd cli/orgctl
npm run build      # → dist/
npm test           # contract tests
```

### `cloud/server` — Express + Prisma backend

```bash
cd cloud/server
npm run db:generate    # required after any schema change
npm run build          # tsc → dist/
npm start              # node dist/index.js
# or for development:
npm run dev            # tsx watch
```

Default port: see `src/index.ts`.

### `cloud/platform` — signed-in web SPA

```bash
cd cloud/platform
npm run build      # tsc --noEmit && vite build → dist/
npm run dev        # http://localhost:5174
```

For headless visual testing, dev auth bypass is documented in
`cloud/platform/DEV-AUTH.md` (blank `VITE_CLERK_PUBLISHABLE_KEY` →
fake `dev@local` user).

### `desktop/dash` — local dashboard

```bash
cd desktop/dash
npm run build          # tsc && vite build → dist/ + web/dist/
npm run serve          # http://127.0.0.1:7880, opens browser
npm run web:dev        # vite dev for the SPA only
```

`npm run serve` is the integrated runtime — it serves the built SPA
out of `web/dist/`, the local HTTP API on 7880, and proxies lens at
7878 if present.

### `desktop/lens` — transcript reader

```bash
cd desktop/lens
npm run build:server   # tsc → dist/ (server only — see Known issues)
npm run serve          # http://127.0.0.1:7878
```

### `web/` — marketing site

```bash
cd web
npx vite build         # → dist/  (see Known issues for why not `npm run build`)
npm run dev            # http://localhost:5173
```

## End-to-end smoke test: `craw init` → Dash

After `craw` is on PATH:

```bash
# Terminal 1 — start dash
cd desktop/dash && npm run serve   # http://127.0.0.1:7880

# Terminal 2 — scaffold a project
mkdir -p ~/tmp/test-craw && cd ~/tmp/test-craw
craw init                          # prints "created"
```

Open `http://127.0.0.1:7880/projects`. You should see:

- **No org linked yet** → folder appears in the "Waiting to sync" panel.
  Sign in on the portal; the drain loop attaches it within 30s.
- **Org linked** → folder shows as a `Local only` project row immediately.

Offline path: stop dash, `craw init` somewhere else, start dash again.
The queued entry surfaces within ~5s (the SPA polls the pending endpoint
on a 5s timer; dash drains the queue on boot).

Sanity check the queue file directly:

```bash
cat ~/.crawfish/pending-projects.json
```

## Known issues

These are preexisting (not from current slices) but break some
`npm run build` invocations:

1. **`web/vite.config.ts` references `node:path` and `__dirname`** but the
   submodule has no `@types/node`, so `tsc --noEmit` fails. `vite build`
   itself works fine. Workaround: skip the typecheck:

   ```bash
   cd web && npx vite build
   ```

2. **`desktop/lens/web` imports `desktop/ui/tokens/globals.css`** — the
   canonical UI dir is `crawfish/ui/`, so the lens web SPA build fails on
   a missing CSS path. The lens server build is unaffected:

   ```bash
   cd desktop/lens && npm run build:server   # OK
   cd desktop/lens && npm run build          # fails on the web step
   ```

   Fix: update lens's Vite/tsconfig paths to point at `../../ui` instead
   of `../ui`. Until then, run the web build manually if needed.

3. **CSS source of truth lives in `ui/tokens/globals.css` only.** Both
   `desktop/dash/web` and `desktop/lens/web` alias `@crawfish/ui` →
   `../../ui` via Vite + tsconfig paths. Don't add component-scoped CSS
   files; extend globals.

## Useful one-liners

```bash
# Typecheck every TS package (no build)
( cd cli/projectctl && npx tsc --noEmit )
( cd cli/orgctl     && npx tsc --noEmit )
( cd cloud/server   && npx tsc --noEmit )
( cd cloud/platform && npx tsc --noEmit )
( cd desktop/dash   && npx tsc --noEmit -p tsconfig.json )
( cd desktop/dash/web && npx tsc --noEmit )

# Run all CLI tests
( cd cli/projectctl && npm test )
( cd cli/orgctl     && npm test )

# Clean every dist/
find . -type d -name dist -not -path "*/node_modules/*" -prune -exec rm -rf {} +
```
