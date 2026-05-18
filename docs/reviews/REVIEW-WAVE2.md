# Wave 2 code review — 2026-05-17

Commits reviewed: `41f80d8..dbc509e` (Wave 2 server scaffold, P2b orgs, P3+D6+D7 device-link, P4 platform canvas, P5 invites, dev.sh changes).
Files reviewed: ~22 source files across `crawfish-server/`, `crawfish-platform/src/`, `crawfish-dash/src/server/link.ts`, `crawfish-dash/web/src/App.tsx`, and `dev.sh`.

The headline: **the auth middleware fails OPEN, not closed, in production**, and one route uses that bypass to mint anything-goes JWTs. There are several other RBAC and validation gaps. Fix the auth gate first; nothing else matters until that's done.

---

## Critical

### C1. Auth middleware falls through to dev-mode even when `CLERK_SECRET_KEY` is set — full auth bypass in prod
**File:** `crawfish-server/src/middleware/auth.ts:48-58`

The Clerk branch is a `TODO` no-op. When `CLERK_SECRET_KEY` is set, the code enters the `if` block, does nothing, and then **falls through** to the dev-mode shim, which trusts any `X-User-Id` header and silently creates a `User` row for it. Result: in any deployment where Clerk is "configured", an attacker can send `X-User-Id: alice` (or any string) and immediately impersonate or auto-create that user. The route handlers behind `authMiddleware` will treat that arbitrary id as authenticated. The comment in `index.ts:16-17` claims dev-mode is gated on `CLERK_SECRET_KEY` being unset; the implementation does not match that claim.
**Fix:** gate the dev-shim explicitly on `process.env.NODE_ENV !== "production" && !process.env.CLERK_SECRET_KEY`, and when `CLERK_SECRET_KEY` is set respond `501 not_implemented` (or actually verify the Bearer token) — never fall through.

### C2. `X-Crawfish-Token` header is honored before the Clerk branch — any caller can present a dash-issued JWT in place of user auth
**File:** `crawfish-server/src/middleware/auth.ts:36-46`

The JWT branch runs first and sets `req.userId = decoded.sub` from a token whose intended audience was the device-link → dash → server channel only. There is no `aud` claim, no scoping to specific routes, no check that the call is coming from a dash-style endpoint, and once accepted the token is treated as equivalent to a full user session for *every* route. Combined with C1 this is the same impersonation issue from a different angle (and is exploitable even with Clerk correctly enforced, once that's wired). The 90-day TTL on these tokens makes the blast radius large.
**Fix:** add an `aud: "dash-sync"` claim at sign time, verify it at the middleware, and restrict `X-Crawfish-Token` to the small set of routes that need it (e.g. `PUT /api/orgs/:id/agents`). Reject any other route when only that header is present.

### C3. `JWT_SECRET` is auto-generated and persisted to `.env` with no env-mode check — silent prod misconfig writes a secret to disk
**File:** `crawfish-server/src/lib/jwt.ts:16-47`

If `JWT_SECRET` is missing in prod (operator forgot to set it), the code generates a random secret and writes it to `./.env`. That's bad for several reasons: (1) it silently masks a config error in prod; (2) on a stateless container deploy the `.env` write is lost on every restart so every restart issues a new secret, invalidating every issued token, which silently looks like "users keep getting logged out"; (3) `process.cwd()` is whatever the process was started from, which on a typical systemd / docker setup may be `/` or `/app`; writing files there may succeed unexpectedly or fail without surfacing. Combined with C1+C2 this means a misconfigured prod will both accept any `X-User-Id` and rotate JWTs randomly.
**Fix:** if `NODE_ENV === "production"` and `JWT_SECRET` is missing or shorter than 32 chars, throw at boot. Never write to `.env` in any environment — log the generated value in dev only.

---

## High

### H1. `Org.id` lookup also accepts `Org.name` as a slug, but `name` has no `clerkId`-style namespace — name-squatting becomes account-takeover surface
**File:** `crawfish-server/src/routes/orgs.ts:110-114` and `137-145`; `crawfish-server/src/routes/deviceLink.ts:67-103`

`GET /api/orgs/:id` and `PUT /api/orgs/:id/agents` accept either the cuid or the unique `Org.name` (slug). Org names are globally unique (schema line 23) and chosen by the first founder — there's no per-owner namespace. The device-link `POST /api/device-link` does `org.upsert({ where: { name } })` with no check for who owns it. So a user can pre-register `acme` on the platform, and when the real Acme founder runs `crawfish init acme` and clicks "Make online", the device-link upsert silently attaches to the squatter's existing Org row (the membership row is added at redeem time, but the row's id and any prior data is the squatter's). The comment at `deviceLink.ts:69-72` acknowledges this and waves it away ("redemption will fail-safe via the OrgMember upsert") — it does not. Redemption *adds* the founder as a member of the squatter's org, alongside the squatter, and mints them a JWT for it.
**Fix:** scope `Org.name` uniqueness per-owner (composite unique `(ownerId, name)`), or refuse `device-link` upsert when the org exists with members the caller doesn't know about. At minimum, on the redeem path, refuse if the org already has a `founder` membership belonging to someone else.

### H2. `POST /api/device-link/:code/redeem` silently *upgrades* any caller to `founder` of any existing org if they're already a member
**File:** `crawfish-server/src/routes/deviceLink.ts:165-179`

If the signed-in redeemer is already an OrgMember (any role), this code unconditionally promotes them to `founder`. Combine with H1: a squatter who pre-registered `acme` and added themselves as a `contributor` will be auto-promoted to `founder` the moment the real founder redeems. More generally, any redeem of a code is treated as a "I am the founder of this org" signal regardless of prior state.
**Fix:** redeem should only attach the caller as a founder if (a) no founder exists, or (b) the caller is already a founder. Otherwise add as contributor with a "founder requested" flag, or refuse.

### H3. `OrgMember` role enum is unenforced; the `team` role isn't validated against an allowlist anywhere
**File:** `crawfish-server/prisma/schema.prisma:41`, `crawfish-server/src/routes/invites.ts:27`

Schema has `role String @default("contributor") // founder | contributor | viewer` — a comment, not a constraint. The invite Zod schema only allows `owner | contributor` (note: `owner`, not `founder` — a third spelling) and the OrgMember table accepts any string via `tx.orgMember.create({ data: { role: invite.role } })`. So an invite with role `owner` creates an OrgMember with role `owner`, which doesn't appear in the schema comment or in the `PUT /:id/agents` gate at `orgs.ts:152` (`founder | contributor`). Result: a user invited as `owner` cannot sync agents, but the system claims they're an owner. Confused-deputy bugs in the making.
**Fix:** pick one role vocabulary, encode it as a Prisma enum (Postgres) or runtime Zod check on every write, and make `owner` and `founder` either the same thing or distinct everywhere.

### H4. Invite-accept transaction is correct, but the *preview* `/api/invites/:code` leaks the invitee email to anyone with the code
**File:** `crawfish-server/src/routes/invites.ts:172-190`

This route is unauthenticated (correct — needed for sign-in flow), but it returns `email`, `role`, `org.name`, and `org.id`. Anyone who guesses or brute-forces a 12-char base64url code (54 bits) can enumerate which orgs are hiring which addresses. 54 bits is fine cryptographically, but: (a) revoked invites just `delete` the row (line 165), no audit trail, no rate limit on guesses; (b) the response also includes `org.id` (cuid), which is then usable as a routing key elsewhere. Lower-impact than auth bypass but it's PII leakage via an unauthenticated endpoint with no rate limiting.
**Fix:** return only `org.name` and `role` in the preview; do not echo `email` (the user already knows their own email) and do not return the org cuid. Add per-IP rate limit (`express-rate-limit`).

### H5. `loadOrgWithRelations` returns every member's email + display name to any single member of the org — there's no membership-visibility gate
**File:** `crawfish-server/src/lib/orgs.ts:14-19`, called by `orgs.ts:121`

Once a user is added to an org (via invite or device-link) they can `GET /api/orgs/:id` and harvest every member's email. For a "team" product this is mostly expected, but combined with H2 (auto-promotion to founder on device-link redeem) and H1 (name-squatting), it means a squatter who pre-creates `acme` and gets a real Acme employee to redeem a code will pull every Acme member's address.
**Fix:** less severe once H1/H2 are fixed; consider hiding emails behind `member.role === "founder"` for non-founders.

### H6. CORS allowlist is dev-only with no prod fallback — first prod deploy will get bitten or someone will set `origin: "*"` in a hurry
**File:** `crawfish-server/src/index.ts:10-13`

`origin: [regex for localhost:5173/5174/7881]` only — there is no env-driven origin allowlist for prod. When the platform ships, someone will either (a) hard-code a prod domain into the same regex (still inflexible) or (b) widen to `*` under deadline pressure. `credentials: true` with `*` is a CORS spec violation and most browsers refuse — but if they ever do allow it (`origin: true` reflect-back is a common quick-fix), it's CSRF surface. Note as a future trap.
**Fix:** read `ALLOWED_ORIGINS` from env (comma-split), default to the dev regex only when `NODE_ENV !== "production"`, and fail boot in prod if env is unset.

### H7. No rate limiting anywhere; org-create, invite-create, and device-link `POST` are all unauthenticated or trivially auth'd and hit the DB on every call
**File:** `crawfish-server/src/index.ts` (no rate-limit middleware), `crawfish-server/src/routes/deviceLink.ts:51` (no-auth), `crawfish-server/src/routes/invites.ts:54` (auth'd but no per-org cap)

`POST /api/device-link` is fully unauthenticated and on every call upserts an `Org`, deletes+recreates AgentMeta, and creates a `DeviceLinkCode`. With ~54 bits of org-name regex and no rate limit, an attacker can enumerate or DoS the table. `POST /api/orgs/:orgId/invites` lets a single founder spam unlimited invites. The scope note says "Note as findings but don't expect fixes in MVP" — flagging for the next sprint.
**Fix:** add `express-rate-limit` (e.g. 30/min per IP on device-link, 10/min per user on invite-create) before any GA traffic.

### H8. `name`-squatting also poisons `Org` denormalized fields on every device-link
**File:** `crawfish-server/src/routes/deviceLink.ts:72-84`

The upsert's `update` branch overwrites `project`, `teamSize`, and `primaryClient` from the *anonymous, unauth'd* request body every time. A squatter can hold the name, then any victim hitting "Make online" with their real metadata silently rewrites the squatter's row — which then immediately shows in the platform UI for the squatter. Also: this is an anonymous endpoint that can mutate existing DB rows.
**Fix:** in the `update` branch, only set fields if the org has no `founder` yet; once a founder exists, ignore anonymous updates.

---

## Medium

### M1. `POST /api/orgs` does `tx.org.create` then `tx.orgMember.create` inside `$transaction` — good — but does not re-check that the org slug is locally unique before relying on a P2002. Race window is short but error message leaks the name back to the caller.
**File:** `crawfish-server/src/routes/orgs.ts:64-98`

`return httpError(res, 409, "name_taken", \`Org name ${body.name} already exists\`)` confirms the existence of an org with that name to anyone who tries — name-enumeration oracle. Combined with H1, this lets a would-be squatter probe which slugs are taken.
**Fix:** return a generic `name_unavailable` message; do not echo the requested name.

### M2. `GET /api/orgs/:id` returns `404 not_found` to non-members and `403 forbidden` to members — leakage oracle for org existence
**File:** `crawfish-server/src/routes/orgs.ts:110-119`

The `findFirst` runs first (404 if absent), then the membership check (403 if present-but-not-member). This means a non-member can distinguish "org with this slug exists" (403) from "doesn't exist" (404). The task brief specifically calls this out — confirmed leakage.
**Fix:** collapse both into `404` so non-members cannot enumerate.

### M3. Same leakage shape in invites and device-link routes
**File:** `crawfish-server/src/routes/invites.ts:43-49` (404 vs 403), `deviceLink.ts:122` (not_found vs other statuses)

Same pattern: existence is implicitly disclosed. Lower-impact since the orgId in URL is usually known to the caller, but consistent fix would help.
**Fix:** unify 403/404 for unauth'd or non-member callers.

### M4. `DELETE /api/orgs/:orgId/invites/:inviteId` allows any member to revoke any invite, not just founders or the creator
**File:** `crawfish-server/src/routes/invites.ts:149-167`

A `viewer`-role member (if that role gets used) could revoke pending invites. Also, no audit log of who revoked.
**Fix:** require `founder` (or `creator === userId`) to revoke.

### M5. `EMAIL_MISMATCH` check is case-insensitive on both sides — verified safe; but `user.email` can be `""` and the comparison would silently match an invite for `""`
**File:** `crawfish-server/src/routes/invites.ts:212`

Case handling is fine (`.toLowerCase()` on both). However if a `User` row exists with `email: ""` (the schema requires `String @unique` but `""` is a valid string), and someone creates an invite with an empty/invalid email that slips past Zod (`.email()` rejects empty so probably safe in practice), the comparison would match. Defensive: also require both sides non-empty.
**Fix:** add `if (!user.email || !invite.email) return 403`.

### M6. Invite-accept reads invite, then opens a transaction — TOCTOU race on double-click can call `tx.orgMember.upsert` twice but the second `tx.invite.update` will still set `redeemedAt`. Net effect benign (idempotent), but the `redeemedById` of the *second* clicker wins.
**File:** `crawfish-server/src/routes/invites.ts:197-233`

The pre-transaction checks at lines 197-207 (`redeemedAt`, `expiresAt`) are not re-validated inside the `$transaction`. SQLite's default isolation gives some protection, but on Postgres (planned) two concurrent accepts would both pass the initial guard, both run the `upsert` (no-op on the second), and both try `tx.invite.update({ where: { id } })` — the last write wins. Since `code` is `@unique`, neither will fail; the membership is idempotent so OK; the redeemed timestamp is overwritten — minor data loss but not a security issue. Single-user double-click is not a real race because the user is the same.
**Fix:** inside `$transaction`, do a conditional update like `tx.invite.updateMany({ where: { id, redeemedAt: null }, data: {...} })` and check `count === 1`; if zero, throw `already_redeemed`.

### M7. `device-link` GET races: same-tab double-poll hands out the same `authToken` twice, then the second delete is a no-op
**File:** `crawfish-server/src/routes/deviceLink.ts:116-138`

The "single-use" comment promises one-shot, but the read-then-delete is not atomic. Two concurrent polls (e.g. the same Dash poller plus a stray retry) will both see the same `authToken`, both will hand it back, and both will try to delete. The `.catch(() => {})` on the delete swallows the error. The token is the same in both responses so the *secret* isn't duplicated, but it is exposed twice over the wire when the design says once. With JWTs valid for 90 days, this is a meaningful re-exposure window.
**Fix:** use `prisma.deviceLinkCode.deleteMany({ where: { code, redeemedAt: { not: null } } })` to atomically claim, then return the token only if `count === 1`.

### M8. `ensureDevUser` race — concurrent first-requests with the same `X-User-Id` will both hit `upsert` and one will error
**File:** `crawfish-server/src/middleware/auth.ts:11-26`

`upsert` on the `email` unique field is atomic in Prisma but error handling is missing — if SQLite hits a brief lock both requests may have one fail with a transient error. Low-impact in dev, but the surrounding `try { … } catch` returns a 500. Not user-visible since dev only.
**Fix:** wrap in retry, or accept since this is dev-only after C1 is fixed.

### M9. `OnlineLink` poll uses `setInterval` against a server-side TTL but the client cap (10 min) is wallclock-only and pauses with tab throttling
**File:** `crawfish-dash/web/src/App.tsx:174-207`

`Date.now() - startedAt > 10 * 60 * 1000` and 2000ms `setInterval`. If the user backgrounds the tab, the interval throttles to ~1Hz; the wallclock cap still fires on the next tick. Server-side TTL is also 10 min so even if the client never times out, the server returns 410. Verified server-side limit is enforced. The minor issue: the code is `setState({ kind: "requesting", code, verifyUrl })` and the `code` lives in component state — if the user navigates away and back, the polling state is lost but the server-side code is not invalidated. No leak (the code expires server-side), but the UX shows "offline" while a code is still live.
**Fix:** acceptable for MVP. Document.

### M10. `Link.tsx` redeem error handling: `error?.code === "not_found"` etc. — case mismatch with server which sends lowercase, but the public route at `deviceLink.ts:153` returns `code: "already_redeemed"` plain string — matches. Verified.
**File:** `crawfish-platform/src/pages/Link.tsx:87-91`

OK as-is.

### M11. Org `name` regex divergence: server `orgs.ts` allows `[a-z0-9][a-z0-9-]*` (dashes only), `deviceLink.ts` allows `[a-z0-9][a-z0-9_-]*` (dashes and underscores). A name with `_` created by Dash via device-link cannot be re-created via `POST /api/orgs`.
**File:** `crawfish-server/src/routes/orgs.ts:29` vs `crawfish-server/src/routes/deviceLink.ts:42`

Subtle but real divergence.
**Fix:** pick one regex, share it from `lib/orgs.ts`.

### M12. `invites.ts` mock-email console.log will print the invite link in prod if `RESEND_API_KEY` is unset
**File:** `crawfish-server/src/routes/invites.ts:91-94`

There is no `if (process.env.NODE_ENV !== "production")` gate on the mock-email log. The link contains the invite code in plain text in stdout, which in most prod log pipelines means PII (email) + a secret (code that grants org membership for 7 days) ends up in log search. Lower than C1 only because logs are usually access-controlled, but flag this — it will be the kind of thing that ends up in Datadog and stays there.
**Fix:** suppress in prod, or strip the code from the logged message.

### M13. `invites.ts:135-145` returns `code` to founders in pending-invite listing when `NODE_ENV !== "production"` — verified prod-safe via `isDev` gate. OK.
**File:** `crawfish-server/src/routes/invites.ts:135-145`

Correct: `isDev = process.env.NODE_ENV !== "production"`. Founders in prod don't see the raw code in the list response.

---

## Low

### L1. `unwrap` in `crawfish-platform/src/lib/api.ts:74-87` parses error body but does not include status in user-facing message — minor DX.
### L2. `OrgMembers.tsx:24` has `void _accept` to silence an unused import — just remove the import.
### L3. `OnboardingFlow.tsx:50` — `Math.max(0, STAGES.indexOf((step as Stage) ?? "welcome"))` allows `/onboarding/garbage` to silently render the welcome stage. Probably fine but inconsistent with `*` catch-all route.
### L4. `dev.sh:11` comment says "kills all four cleanly" but the script now runs five processes.
### L5. `dev.sh:79` echo says "all four surfaces up" — should be "five".
### L6. `crawfish-server/.env.example` has a `RESEND_API_KEY` placeholder commented out — verified safe (placeholder, no real key).
### L7. `crawfish-server/.env` (not committed; verified via `git check-ignore`) contains a real-looking `CLERK_SECRET_KEY="sk_test_FShPE6iPcLU8C82yptb3wHZSSsPMGPrYFptMnabTod"` on disk. The `.gitignore` correctly excludes it so it has never entered git, but the user should rotate this key in Clerk's dashboard out of an abundance of caution since I have now read it. Verified the example file does not contain it.
### L8. `loadOrgWithRelations` (`lib/orgs.ts:7`) does not paginate `members`/`agents` — a large org will return everything in one response. MVP-acceptable.
### L9. `OnboardingFlow.tsx:120-123` — `setTimeout(() => go("hired"), 1400)` is not cleared on unmount (the outer `cancelled` flag is checked inside the callback, but the timer itself leaks). Tiny.
### L10. `InviteAccept.tsx:267-285` — `redirect` URL is built with `encodeURIComponent` (good) but consumer of `?redirect=` (sign-in page) is not in the diff; verify that it validates the redirect target is same-origin to avoid open-redirect.
### L11. `OrgPicker.tsx:126` slices org name `o.name.slice(0, 2)` for the avatar tile — for an org named `_x` (underscore-led, per the divergent regex in M11) the slice will include the underscore which looks odd. Trivial.
### L12. `deviceLink.ts:23` excludes `I/L/O/0/1` from the code alphabet (good — avoids confusables) and uses `nanoid/non-secure`. **`non-secure` is the wrong import for a token used as authentication material** — even though the TTL is 10 minutes, this is a token that grants org-founder access on redeem. Use `nanoid` (the default secure variant) or `crypto.randomBytes`. Re-classifying as **High** actually:

### H9 (promoted from L12). Device-link code generated with `nanoid/non-secure`
**File:** `crawfish-server/src/routes/deviceLink.ts:16`

`customAlphabet` from `nanoid/non-secure` uses `Math.random()`, which is not cryptographically secure. The code (6 chars from a 32-letter alphabet → ~30 bits of entropy at best, less with `Math.random` predictability) is the sole secret a redeemer needs to claim founder of the org. An attacker who can observe a server's PRNG state (e.g. via timing or shared state in a worker pool) can guess valid pending codes. 30 bits is also brute-forceable in seconds against a server with no rate limit (see H7).
**Fix:** import from `nanoid` (default, crypto-backed), and lengthen to 8+ chars from the same alphabet (~40 bits), or use `crypto.randomBytes(4).toString('hex').toUpperCase()`.

---

## Not found / verified-safe

- **Invite accept transaction** *does* wrap `OrgMember.upsert` + `Invite.update` in `db.$transaction` (invites.ts:222-233). The membership upsert handles the double-invite case correctly. The only race concern is M6 above (timestamp clobber on a Postgres deploy), not a security issue.
- **EMAIL_MISMATCH case sensitivity** is handled — both sides `.toLowerCase()` at `invites.ts:212` and the server stores emails lowercased on create (`invites.ts:72`).
- **`.env.example`** contains only placeholders. Verified safe to commit.
- **`writeOrgToken` in `crawfish-dash/src/server/link.ts:44-54`** uses `mode: 0o600` and a follow-up `chmod 0o600` — token is not world-readable.
- **`crawfish-server/.env` is git-ignored** (`git check-ignore` confirmed). The Clerk secret on disk has never been committed.
- **Express `json({ limit: "1mb" })`** is set at `index.ts:14` — bounds unbounded body DoS. Good.
- **`apiFetch` in platform** does not log tokens; the dev-mode `X-User-Id` value comes from `localStorage` and is not logged. No secret leakage in the client.
- **`OnlineLink` server-side TTL** (10 min) is enforced both at `deviceLink.ts:123` and `deviceLink.ts:148`. The client poll cap is redundant defense, not the sole limit.
- **`encodeURIComponent`** is used consistently for URL-segment building in platform and dash. No injection via slug.
- **CORS `credentials: true` + allowlist regex** is correctly closed (not `*`) — dev-safe. See H6 for the prod follow-up.

---

_Reviewed by: Claude (gsd-code-reviewer)_
_Depth: deep_
_Files reviewed: 22_
