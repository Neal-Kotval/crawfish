# crawfish-web E2E tests

Playwright suite for the marketing front door.

## Run

```bash
npm run test:e2e          # headless
npm run test:e2e:ui       # Playwright UI mode
```

The config boots `npm run dev` automatically (or reuses a running instance
outside CI) and points `baseURL` at `http://127.0.0.1:5173`.

## Coverage

### `index.spec.ts`

- Hero eyebrow + headline render (current copy from `src/pages/Index.tsx`).
- Github nav link and "Invite a teammate later" CTA resolve to the expected hrefs.
- Platform-detect: three independent describe blocks set the browser
  `userAgent` to mac / linux / windows and assert the primary install card
  shows the matching `Download for ...` label.

### `release-fetch.spec.ts`

- Mocks `api.github.com/.../releases/latest` via `context.route(...)` and
  asserts the primary download button URL swaps to the mocked asset (a
  `.dmg` for the mac UA).
- Mocks a 500 and asserts the page still renders, the primary button falls
  back to a generic releases URL, and no app-level console errors are emitted.

## Caching note

`src/lib/downloads.ts` caches the GitHub release JSON in `localStorage`
under key `cf:release` for 5 minutes. Both release-fetch tests use an
`addInitScript` to `localStorage.clear()` before navigation so a previous
run's cached payload cannot leak in.
