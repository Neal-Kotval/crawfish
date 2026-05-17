# Crawfish — MVP roadmap

The 4-phase roadmap in `ROADMAP-FUNCTIONALITY.md` is the long view.
This is the MVP: what we actually need to ship a working v0 that
proves the brand promise.

**Brand promise** (lifted verbatim from the marketing hero):
> Hire your company in fifteen minutes. Local-first. MIT. No card required.

Everything not in service of that promise is cut.

---

## MVP shape: two waves

### Wave 1 — local-first MVP (week 1–2)

Ship the local-first flow standalone. No platform, no auth, no
backend. A founder can:

1. Land on **crawfish.dev**.
2. Download **Dash** for their platform.
3. Open it. The built-in **first-run wizard** asks the four
   onboarding questions, writes `~/crawfish/<org-name>/`, and seeds
   four agents.
4. Click **Hire Eng-bot**. A real Claude Code session opens against
   a starter repo. The live trace shows reads, edits, test runs.
   A pull request opens locally.

That's it. No account, no cloud, no sync. The dash is the whole
product. The platform is dark.

**Definition of done**: a recorded 15-minute video, no cuts, from
crawfish.dev to PR open. Posted to the hero.

### Wave 2 — web platform layer (week 3–4)

Add account portability on top of the local-first flow. Same Dash,
same agents, same on-disk org folder — but now optionally synced to
an account so the same org is reachable from another machine, from
the web, and from teammates.

A founder can:

5. Click **"Make this org online"** in Dash → device-code flow links
   to `app.crawfish.dev`.
6. **Sign up** on the platform (Clerk/GitHub OAuth).
7. The org's metadata (members, settings, session permalinks)
   syncs to the platform DB. Files stay on disk.
8. **Invite a teammate by email.** They sign up, open the platform
   in their browser, see the org canvas read-only with a "Download
   Dash to contribute" CTA.

That's it. No multi-cursor canvas, no real-time collaboration, no
billing. The platform is a thin sync layer + a read-only viewer.
Multi-cursor and billing land in v0.2.

**Definition of done**: a second 5-minute video showing a founder
invite a teammate, the teammate sign up on web, and view the same
org in their browser.

---

## Wave 1 — local-first MVP (week 1–2)

### Marketing (`crawfish-web/`)

**M1. Real download URLs.** `Index.tsx` currently has dead
`PlatBtn` buttons.
- Detect platform via `navigator.userAgentData` (with userAgent
  fallback).
- Fetch latest release from
  `https://api.github.com/repos/<org>/crawfish/releases/latest`,
  cached for 5 min in `localStorage`.
- Set the primary CTA href to the matching `.dmg` / `.AppImage` /
  `.msi` asset URL. Other-platform buttons become secondary.
- If the fetch fails, fall back to a link to the releases page.

**M2. Hide what doesn't work.** Comment out the `/product`,
`/templates`, `/pricing`, `/roadmap`, `/docs` nav items in the
header. Leaving them as stubs reads "abandoned." Keep `Sign in` +
`Create org` greyed-out with a tooltip "v2 — coming soon" *or*
remove them entirely. Recommend: remove. The hero is enough.

**M3. The "Step 1 of 3" copy is misleading** (there's no step 3 on
this page). Reword: replace "Step 1 of 3 · pick your starting
client" with just "Pick your client." Drop the "2" badge in the
dashed device-code strip; reword to "After install, your client
runs locally — `~/crawfish/<org>/`."

**No backend. No analytics. Ship the static site to Vercel/Cloudflare
Pages with a 1-line domain config.**

### Dash (`crawfish-dash/`)

**D1. First-run wizard wired into cold launch.** A new `crawfish-dash`
install with no orgs on disk should immediately render the
onboarding flow (port the 5-stage flow from `crawfish-platform/src/
onboarding/OnboardingFlow.tsx` into a Tauri-native version under
`crawfish-dash/web/src/wizards/first-run/`). The existing wizard at
that path is the legacy four-tab one — replace it.

The wizard writes to disk:
- `~/crawfish/<org>/crawfish.toml` (org metadata: name, project,
  team size, primary client)
- `~/crawfish/<org>/agents/<agent>.yaml` (one per proposed agent)
- `~/crawfish/<org>/knowledge/api-conventions.md` (seed file)
- `~/crawfish/<org>/policies/default.yaml`

The "install streaming" stage of the wizard shows real progress as
each file lands. The "hired" stage routes to `/canvas` with the
org loaded.

**D2. Canvas reads from disk, not seed data.** Replace
`seedAgents` in `Canvas.tsx` with a Tauri command
`list_agents(org_id)` that walks `~/crawfish/<org>/agents/*.yaml`
and returns them. Agent positions on the canvas: store in
`~/crawfish/<org>/canvas.json` (a `{ agent_id: {x, y} }` map),
default to a clean grid if missing, persist on drag.

**D3. One real agent, one real task.** The "Hire agent" button
spawns a Claude Code SDK session (or shells out to `claude-code`)
against a fixed starter repo (`crawfish-starter-app/`, a tiny
Express server checked into the repo) with the task:
> Add a `/healthz` endpoint that returns `{ status: "ok" }`.

The session events stream into the right rail's live trace via
SDK callbacks. Token + cost accumulate in real time. On finish,
the trace shows "PR opened" and links to a `git diff`.

This is the demo. Everything else is decoration around this.

**D4. Hide what's not wired.** The five sidebar items (Canvas,
Board, Sessions, Knowledge, Diagnoses) — Canvas works, the other
four are `Placeholder` stubs. For MVP: hide Board, Sessions,
Knowledge, Diagnoses entirely. The MVP dash has *one* surface.
The other four come back in Wave 3 of the long roadmap.

**D5. Tauri shell polish.** Custom titlebar is already wired
(traffic-light overlay). Confirm:
- Cmd+Q quits cleanly.
- Window position persists between launches (`tauri-plugin-window-
  state`).
- The deep-link handler is registered for `crawfish-dash://` so
  Wave 2's link-from-web flow works without re-shipping.

### What's NOT in Wave 1

- The platform (`crawfish-platform/`) — runs locally for dev, not
  shipped.
- Auth, sync, accounts, teams, billing, sharing.
- Multi-cursor, presence, real-time anything.
- The Board / Sessions / Knowledge / Diagnoses dash routes.
- A docs site. A pricing page. A roadmap page.
- Anything in the IDE or CLI.

---

## Wave 2 — web platform layer (week 3–4)

Only start after Wave 1 ships and someone non-team has used it.

### Platform (`crawfish-platform/`)

**P1. Auth via Clerk.** Drop in `<SignIn />` and `<SignUp />` from
`@clerk/react`. Wire to GitHub OAuth + email magic-link. No
custom forms.

**P2. Org sync API.** `POST /orgs` (create), `GET /orgs/:id`
(read), `GET /me/orgs` (list). Backed by Postgres + Prisma on
Vercel/Neon. Schema: orgs, org_members, sessions (metadata only —
no transcripts), device_link_codes.

**P3. Device-link.** `POST /device-link` returns a 6-char code.
The Dash side calls `POST /device-link/:code/redeem` with the org
metadata; on match, returns an auth token. The platform UI shows
"Waiting for Dash..." then "Linked ✓ — open it now."

**P4. Read-only online canvas.** Reuse the Node + Pill primitives.
`GET /orgs/:id/agents` returns the same shape as Wave 1's disk-
read. The online canvas is *not* multi-cursor — it's a snapshot.
The text below it says "viewing as <user>; install Dash to
contribute."

**P5. Invite by email.** Platform `/orgs/:id/team` has an email
input + "Send invite." Backend sends an invite link via Resend/
Postmark; clicking it routes to sign-up; on sign-up, the user is
added as an org_member.

### Dash (`crawfish-dash/`)

**D6. "Make this org online" button.** Above the org switcher in
the titlebar. Click → opens browser to `app.crawfish.dev/link/
<code>`. After redeem, Dash stores the auth token and starts
syncing org metadata on every change.

**D7. Sync agent metadata** (not files) to the platform after
every edit. Files stay local — this is just so the online canvas
view stays in sync.

### What's NOT in Wave 2

- Multi-cursor / real-time collab.
- Billing / Stripe.
- The full Board / Sessions / Knowledge / Diagnoses surfaces on
  the platform (they're empty pages until v0.2).
- Public session permalinks.
- Org roles + ACL.

---

## Hard cuts (out of MVP, both waves)

| Cut | Why | Where it lives later |
|---|---|---|
| Pricing page | Pre-revenue, free through v0 | Long roadmap phase 4 |
| Docs site | One README.md is enough for week 1–4 | Long roadmap phase 4 |
| Roadmap page | This file is the roadmap | Long roadmap phase 4 |
| Templates marketplace | One template per agent role hardcoded | Phase 5 |
| Multi-cursor canvas | Liveblocks is 2 days of plumbing for 0 MVP users | Phase 3 |
| Stripe billing | Free tier through v0 | Phase 3 |
| Mobile | Dash is desktop-only by design | Never |
| IDE plugin | Separate workstream | Phase 5 |

---

## Operational decisions (cuts in half if MVP is local-first)

Wave 1 needs **none** of these — it's all local. Wave 2 needs:

1. **Auth**: Clerk. (Decided. Cheapest path.)
2. **Backend**: Postgres on Neon + Prisma on Vercel. (Not Convex —
   no real-time required for Wave 2 since the online canvas is a
   snapshot, not multi-cursor.)
3. **Hosting**: Vercel for both `crawfish-web/` and
   `crawfish-platform/`. Subdomains: `crawfish.dev` (marketing) +
   `app.crawfish.dev` (platform).
4. **Dash distribution**: GitHub Releases. Tauri auto-update
   later.

---

## Sequenced day-by-day (Wave 1)

| Day | Work                                                                            |
|-----|---------------------------------------------------------------------------------|
| 1   | M1 (download URLs) + M3 (copy) + M2 (hide nav). Deploy marketing to Vercel.     |
| 2   | D1 part 1 — wire FirstRunWizard into Dash cold launch, write `crawfish.toml`.   |
| 3   | D1 part 2 — write agents/knowledge/policies files, route to `/canvas` on done.  |
| 4   | D2 — Canvas reads from disk via Tauri commands. Drag positions persist.         |
| 5   | D3 part 1 — wire Claude Code SDK to Hire button; spawn session w/ starter repo. |
| 6   | D3 part 2 — stream events into right-rail live trace, real token/cost numbers.  |
| 7   | D3 part 3 — PR opens, trace shows "PR opened" with link. Test full flow E2E.    |
| 8   | D4 (hide stub surfaces) + D5 (Tauri polish: window state, quit, deep-link reg). |
| 9   | Cut Dash v0.5 release. Bump tauri.conf.json version. Sign + notarize macOS.     |
| 10  | Record the 15-min video. Publish to crawfish.dev hero. Tag the release.         |

If this slips into week 3, Wave 2 slips proportionally. That's
fine — Wave 1 has to be solid before Wave 2 has any reason to
exist.

---

## Success metric for MVP

Not signups. Not GitHub stars. **One specific metric**: how many
distinct GitHub usernames open a PR that was authored by a Crawfish-
spawned agent in the 30 days after launch. If that number is
≥10, the MVP worked. If it's <3, the brand promise is wrong, not
the code.
