# Running crawfish

Five components — desktop shell wraps the web stack; each can also run standalone.

## crawfish-app — Tauri desktop shell

```sh
cd crawfish-app
npm install
npm run dev          # cargo tauri dev
npm run build        # cargo tauri build
bash ../scripts/build-dmg.sh   # signed/zipped .dmg
```

Requires Rust + `cargo tauri` CLI.

## crawfish-dash — agents dashboard (server + web UI)

```sh
cd crawfish-dash
npm install
npm run dev          # CLI / server entry (tsx src/index.ts)
npm run serve        # start the HTTP server only
npm run web:dev      # Vite dev server for the React UI
npm run build        # tsc + vite build
```

Two-process dev loop: `npm run serve` in one terminal, `npm run web:dev` in another.

## crawfish-lens — token-usage observability

```sh
cd crawfish-lens
npm install
npm run dev          # CLI
npm run stats        # token stats over ~/.claude transcripts
npm run sessions     # list sessions
npm run serve        # localhost dashboard server
npm run web:dev      # Vite dev UI
npm test             # vitest
```

## crawfish-opt — semantic browser MCP

```sh
cd crawfish-opt
npm install          # postinstall pulls Playwright chromium
npm run build
npm start            # node dist/index.js
npm run benchmark:vs-stagehand
```

Needs `.env` with API keys for the benchmark scripts (`--env-file=.env`).

## Top-level

```sh
git submodule update --init --recursive   # first checkout
```

UI tokens live in `ui/tokens/globals.css`; shared components in `ui/components/`.
