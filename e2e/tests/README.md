# Crawfish umbrella E2E

One Playwright suite at the repo root covering:

- **crawfish-platform** (Vite, port 5174) — onboarding, OrgPicker, OrgRoute canvas, OrgMembers / invites.
- **crawfish-dash** web shell (Vite, port 7881) — SignInGate, AccountPanel, canvas, OnlineLink pill.
- **crawfish-server** (Express + Prisma, port 7882) — dev-mode auth shim used by helpers.
- **dash node API** (port 7880) — used to seed local orgs.

The marketing site (`crawfish-web`) has its own Playwright suite at
`crawfish-web/tests/e2e/`. It is intentionally NOT duplicated here — run it
separately with `npm run test:e2e` from that submodule.

## Prerequisites

The runner does NOT start dev surfaces. Bring them up first:

```bash
./dev.sh
```

Then in another terminal:

```bash
cd e2e
npm install
npx playwright install chromium
npm test
```

If any surface is down, tests fail with `ECONNREFUSED`.

## Suite layout

| Spec                                       | Covers                                                          |
| ------------------------------------------ | --------------------------------------------------------------- |
| `01-platform-auth.spec.ts`                 | Dev-mode auth gate; skips cleanly when Clerk is configured.     |
| `02-platform-onboarding.spec.ts`           | Full 5-stage wizard + 409 duplicate-name retry.                 |
| `03-platform-orgs.spec.ts`                 | OrgPicker empty/seeded; canvas tab + Open-in-Dash href shape.   |
| `04-platform-invites.spec.ts`              | Create, mock-email, revoke, accept-as-invited, 404.             |
| `05-platform-open-in-dash.spec.ts`         | Cross-surface bridge: clicking Open-in-Dash boots dash linked.  |
| `06-dash-signin-gate.spec.ts`              | SignInGate hides shell; testid + portal href; gate dismissal.   |
| `07-dash-account-page.spec.ts`             | Avatar opens /settings/account; Unlink returns to the gate.     |
| `08-dash-canvas-and-onlinelink.spec.ts`    | Canvas renders default agents; OnlineLink pill via mocks.       |

## Notes

- `playwright.config.ts` sets `fullyParallel: false` + `workers: 1`. The
  three surfaces share SQLite and an on-disk org directory; running in
  parallel races them.
- `global-setup.ts` wipes both: it `prisma db push --force-reset`s
  `crawfish-server/` and removes any `~/crawfish/e2e-*` dirs from prior
  runs. Real on-disk orgs (anything without an `e2e-` prefix) are left
  alone.
- Tests use the platform server's dev shim by sending `X-User-Id` /
  `X-User-Email` headers. No Clerk required.
