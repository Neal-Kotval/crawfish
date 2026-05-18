# Dev auth bypass — for visual-audit agents

If you're an agent (ui-auditor, ui-diagnose, Playwright-based reviewer) trying
to walk the signed-in surfaces of the Crawfish web platform and you're getting
bounced to `/signin` by Clerk, **do not try to complete GitHub OAuth headlessly
and do not ask the user for their credentials.** The codebase already has a
first-class dev bypass. Use it.

---

## How auth resolves

`cloud/platform/src/lib/clerk.ts` exports:

```ts
export const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;
export const CLERK_ENABLED = Boolean(CLERK_KEY);
```

- **Key set** → Clerk owns auth. `<RequireAuth>` bounces unsigned users to `/signin`.
- **Key empty/unset** → dev mode. `useCurrentUser()` returns a fake user
  (`id: "dev-user"`, `email: "dev@local"`, `isSignedIn: true`), `RequireAuth`
  lets every route through, and `apiFetch` sends `X-User-Id: dev-user`
  instead of a JWT.

The backend honors the dev shim at
`cloud/server/src/middleware/auth.ts:7` via the `x-user-id` header when
`NODE_ENV !== "production"`.

---

## Activation steps

1. Create or edit `cloud/platform/.env.local` (Vite loads it after `.env` and
   it wins; both files are gitignored):

   ```
   VITE_CLERK_PUBLISHABLE_KEY=
   VITE_SERVER_URL="http://127.0.0.1:7882"
   ```

   The blank value is what disables Clerk — `Boolean("")` is `false`.

2. **Restart the Vite dev server** in `cloud/platform`. Vite reads env files
   once at boot; an HMR reload is not enough. If the server was already
   running when you arrived, ask the user to restart it — per
   `/Users/nealkotval/crawfish/CLAUDE.md`, agents must not kill processes
   they didn't start.

3. **Start `cloud/server`** if it isn't running (`cd cloud/server && npm run dev`,
   default port `:7882`). Without it, every `/api/*` call returns
   `ERR_CONNECTION_REFUSED` and every data-driven surface renders its error
   state instead of its real state — your screenshots will be misleading.

4. Load `http://localhost:5174/`. You should land on the org picker (`/`) as
   `dev@local` with no Clerk widget in the way.

---

## Verifying you're in dev mode

Quick sanity checks before you start the audit:

- `document.querySelector('[data-clerk-component]')` returns `null` on `/signin`.
- DevTools → Network → any `/api/*` request → request headers include
  `X-User-Id: dev-user` and **no** `Authorization: Bearer ...` header.
- The avatar initial in the titlebar is `D` (first letter of `dev`).

If any of those fail, the env override didn't take — most likely cause is
that Vite wasn't restarted.

---

## Seeding data

A fresh `dev@local` account has no orgs and no projects. To audit the rich
surfaces (Canvas, Projects, Team) you need data. Two options:

- **Use the onboarding flow.** `/onboarding/welcome` creates an org end-to-end.
  Works in dev mode.
- **Seed directly.** `cd cloud/server && npm run db:seed` (if the script
  exists in `package.json`) or hit the API:
  ```bash
  curl -X POST http://127.0.0.1:7882/api/orgs \
    -H 'content-type: application/json' \
    -H 'x-user-id: dev-user' \
    -d '{"name":"audit-org","primaryClient":"Dash","teamSize":"Just me"}'
  ```

For projects, use the GitHub import path only if `cloud/server` has a GitHub
token configured. Otherwise fake it with the `/api/orgs/:orgId/projects`
POST endpoint directly.

---

## Reverting to Clerk

Delete `cloud/platform/.env.local` (or set `VITE_CLERK_PUBLISHABLE_KEY` back
to the `pk_test_...` value in `.env`) and restart Vite. The original `.env`
is untouched.

---

## Why not just complete OAuth headlessly?

- GitHub's OAuth page is intentionally bot-hostile (captcha, device checks).
- Even if you scripted the redirect, you'd be pinning your audit to a
  specific human's GitHub account, which is unauditable and unsafe.
- Dev mode is the user-stable, repeatable path — every future agent gets
  the same fake user, so screenshots are comparable across runs.
