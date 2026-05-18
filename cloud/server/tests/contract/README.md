# crawfish-server contract tests

Black-box HTTP tests against the Express app, run with vitest + supertest.
Each spec hits the real Express handlers and the real Prisma client backed by
the dev SQLite DB; the harness wipes that DB once at suite start.

## Run

```bash
cd crawfish-server
npm test          # one-shot
npm run test:watch
```

`npm test` runs `vitest run` against `tests/contract/**/*.spec.ts`. Tests are
sequential (`fileParallelism: false`) because they share one database.

## Coverage

| File | What it locks down |
|---|---|
| `health.spec.ts` | `GET /api/health` → 200 `{ok:true}`. |
| `orgs.spec.ts` | Create org (201, default agents), name conflict (409), invalid name + invalid teamSize (400 Zod), list-mine with counts + role, read by cuid and slug, 403 for non-member, 404 for missing. |
| `invites.spec.ts` | Create / list (with dev `code` exposure) / revoke; public preview; accept happy-path; double-accept (410); expired preview + accept (410); EMAIL_MISMATCH (403); case-insensitive email match. |
| `link.spec.ts` | `POST /api/device-link` (anonymous), pending poll, redeem as a different user, post-redeem poll returns `authToken` and is single-use (404 after), expired code (410), unknown code (404). |

> The ROADMAP refers to `/api/orgs/:id/link`, but the server actually exposes
> `/api/device-link/*` (see `src/routes/deviceLink.ts`). The tests follow the
> real surface.

## DB reset

`setup.ts` runs `npx prisma db push --force-reset --skip-generate` in a
`beforeAll`, then dynamically imports `src/index.ts` so the singleton
`PrismaClient` connects to the fresh schema. The Express `app` is reused
across all specs — supertest gives each request its own ephemeral port and we
never call `app.listen()` from tests.

## Source edits made for this suite (the only ones)

1. **`src/index.ts`** — refactored so `app` is exported and `app.listen()`
   only runs when the file is invoked directly (`process.argv[1]` matches
   `import.meta.url`). Required so tests can `import { app }` without binding
   port 7882.
2. **`src/middleware/auth.ts`** — added an `X-User-Email` dev-mode header.
   When the dev auth shim is active, a request can override the synthetic
   `<id>@local` email so invite-accept flows (which compare the signed-in
   user's email to the invite recipient) are exercisable end-to-end. Real
   Clerk verification, when wired, will set the email from the JWT and this
   header is ignored.

No other source files were touched. The tests are intended to surface
behavior, not paper over it.
