# Wave 3 — verification, hardening, and code review

Two waves shipped a working MVP across five dev surfaces. Wave 3 is the
trust pass: end-to-end Playwright coverage for every user flow, contract
tests on the cloud API, and a code-review sweep over Wave 2 code (the
newest and least battle-tested layer).

No new features. No design changes. The goal is to catch the bugs that
manual clicking missed, lock in the contract between platform ↔ server,
and produce a written review of the auth/RBAC/invite paths.

---

## Surfaces and the flows we test

| Surface | URL | Flows under test |
|---|---|---|
| **marketing** (`crawfish-web`) | :5173 | platform-detect download CTA, install card render, GitHub-release fetch fallback, secondary CTAs |
| **platform** (`crawfish-platform`) | :5174 | dev-mode auth gate, onboarding wizard (5 stages → create org), OrgPicker (empty/loaded/error), OrgRoute canvas read-only, OrgMembers panel (invite + revoke + mock-email surface), `/invites/:code` landing (3 states: anon/match/mismatch), `/invites/:code` accept happy + 410 expired + 404 unknown |
| **dash-web** (`crawfish-dash`) | :7881 | first-run wizard writes org, Canvas reads agents from disk + drag-to-persist, OnlineLink "Make online" device-code panel render (server stubbed), Hire button stream rendering (claude stubbed), sidebar trimmed to wired routes |
| **crawfish-server** | :7882 | health, orgs CRUD + RBAC, invites CRUD + redeem + EMAIL_MISMATCH + expiry, device-link create + poll + redeem |

---

## Task breakdown

### W3.T1 — platform Playwright suite *(largest)*
- New `crawfish-platform/tests/e2e/` with Playwright config, fixtures, helpers.
- Tests:
  - `auth.spec.ts` — dev-mode auth gate; `/signin` → onboarding when no orgs.
  - `onboarding.spec.ts` — full 5-stage wizard, 409 retry, name-regex error.
  - `org-picker.spec.ts` — empty state, loaded list, error toast on 5xx.
  - `org-canvas.spec.ts` — fetch org, render agents read-only, 403/404 paths.
  - `invites.spec.ts` — create invite, mock-email card visible, revoke, public landing page renders 3 states + 410 expired + 404 unknown.
- Spawns crawfish-server in `webServer` config (same SQLite dev DB, fresh on each run via `prisma db push --force-reset`).

### W3.T2 — marketing Playwright suite *(small)*
- New `crawfish-web/tests/e2e/`.
- Tests:
  - `index.spec.ts` — hero renders, platform-detect picks dmg on mac/AppImage on linux/msi on windows (mock `navigator.userAgent`), nav links go to platform.
  - `release-fetch.spec.ts` — mock GitHub Releases API, verify install card swaps to real asset URL on success and falls back to placeholder on failure.

### W3.T3 — dash-web Playwright suite *(medium)*
- New `crawfish-dash/web/tests/e2e/`.
- Tests:
  - `first-run.spec.ts` — wizard writes `~/crawfish/<name>/` (assert via dash node REST), bounces to /canvas.
  - `canvas.spec.ts` — agents render, drag persists position via PATCH.
  - `online-link.spec.ts` — mock crawfish-server `/link` route, OnlineLink panel shows code + polling spinner.
  - `hire.spec.ts` — mock claude CLI subprocess, verify SSE events project into liveTrace.

### W3.T4 — crawfish-server contract tests *(small)*
- New `crawfish-server/tests/contract/` using `supertest` + the existing express app.
- Tests:
  - `health.spec.ts`
  - `orgs.spec.ts` — create (200/409), get-by-id (200/403/404), list-mine, slug + cuid lookup.
  - `invites.spec.ts` — create+list+revoke, public preview (404/410/200), accept (200/403 EMAIL_MISMATCH/410 redeemed).
  - `link.spec.ts` — create code, poll unredeemed, redeem flow.
- Reuses dev SQLite via `prisma db push --force-reset` before suite.

### W3.T5 — code review pass *(read-only)*
- Run the `review` skill on commits `41f80d8..HEAD` on `wk5/stage1-now` — Wave 2 surface area (server + platform + dash OnlineLink).
- Focus: auth middleware bypass paths, Zod validation gaps, EMAIL_MISMATCH case-sensitivity, race conditions in invite-accept transaction, device-link code entropy, missing rate-limits, secrets-in-logs.
- Produce `docs/reviews/REVIEW-WAVE2.md` with findings classified Critical / High / Med / Low.

---

## Run order
T4 + T5 are independent and can run in parallel with T1/T2/T3 (which need dev servers up).

```
parallel: [T1 platform-e2e]  [T2 marketing-e2e]  [T3 dash-e2e]  [T4 server-contract]  [T5 code-review]
serial:   commit each suite separately, push umbrella branch
```

## Definition of done
- `npx playwright test` green in `crawfish-platform`, `crawfish-web`, `crawfish-dash/web`.
- `npm test` green in `crawfish-server`.
- `docs/reviews/REVIEW-WAVE2.md` exists with at least one entry in each severity bucket (or a "none found" note).
- README in each suite directory explains: how to run, what's covered, what's not.
- `dev.sh` unchanged — tests own their server lifecycle.
