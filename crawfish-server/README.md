# crawfish-server

Database-backed Node/Express service that the marketing site, platform, and
Dash all talk to. Owns org sync, device-link, auth, and invites. Express on
port `7882`, Prisma ORM, SQLite for dev (zero setup), Postgres for prod via
`DATABASE_URL`.

## Run it locally

```bash
npm install
cp .env.example .env
npx prisma generate
npx prisma db push        # creates ./dev.db with all tables
npm run dev               # http://127.0.0.1:7882
```

Smoke-test:

```bash
curl http://127.0.0.1:7882/api/health
# {"ok":true}
```

## Env vars

| Var | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | `file:./dev.db` for dev, `postgres://…` in prod. |
| `PORT` | no | Defaults to `7882`. |
| `RESEND_API_KEY` | no | When set, invites send real email; otherwise URLs are console-logged. |
| `CLERK_SECRET_KEY` | no | When set (P1), Clerk JWTs are verified; otherwise the auth middleware trusts `X-User-Id`. |

## Inspecting the DB

```bash
npm run db:studio
```

Opens Prisma Studio in the browser.
