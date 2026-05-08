# @crawfish/ui — shared UI

Canonical UI primitives for the crawfish platform. Imported by **both** `crawfish-lens` and `crawfish-dash` via the `@crawfish/ui` Vite alias. Edit once, ship everywhere.

## Layout

```
ui/
├── tokens/
│   ├── globals.css       # the entire stylesheet (1097 lines, dark+light themes)
│   └── design-tokens.ts  # programmatic access to tokens
├── lib/
│   └── format.ts         # fmtCompact, fmtBytes, fmtMtime, copyToClipboard, etc.
└── components/
    ├── TokenBar.tsx      # 4-bucket token visualization (input/cache_read/cache_write/output)
    └── Finding.tsx       # diagnostics banner with severity icon + fix install command
```

## How it's wired

This folder lives at the **umbrella repo level** (not in any submodule). Each consumer's Vite + tsconfig set up a `@crawfish/ui` alias pointing here:

```ts
// crawfish-lens/web/vite.config.ts (and crawfish-dash/web/vite.config.ts)
resolve: {
  alias: {
    "@crawfish/ui": resolve(__dirname, "..", "..", "..", "ui"),
  },
}
```

Then in any component:

```tsx
import { fmtCompact } from "@crawfish/ui/lib/format";
import { TokenBar } from "@crawfish/ui/components/TokenBar";
import "@crawfish/ui/tokens/globals.css";
```

## Versioning

For now: no version, just `main`. Both submodules pin to the umbrella's HEAD via `git submodule update --remote`. When this folder grows enough to want independent release cadence, extract to its own published `@crawfish/ui` npm package.

## Adding a new shared component

1. Drop the `.tsx` here.
2. Use only tokens + base CSS classes — no per-app styles.
3. Import from `@crawfish/ui/components/<Name>` in the consumer.

## Why not npm workspaces or a published package?

- npm workspaces don't compose well with git submodules (each submodule has its own `package.json` and `node_modules`).
- A published package adds a versioning + release pipeline overhead we don't need yet.
- A relative-path alias works, is reproducible, requires no special setup beyond cloning the umbrella with `--recurse-submodules`.

## Standalone clones of lens or dash

`@crawfish/ui` resolution requires the umbrella checkout. If you `git clone` lens or dash directly, the `../../ui` path won't exist and the build will fail with a clear "module not found" error pointing here. Use the umbrella.
