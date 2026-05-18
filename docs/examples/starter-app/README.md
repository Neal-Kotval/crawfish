# crawfish-starter-app

A tiny Express server used as the target repo for the Crawfish MVP demo.

When the user clicks "Run demo task" in the dash canvas right rail, the
Eng-bot agent (a real `claude` CLI session) is spawned against this repo and
asked to add a `GET /healthz` endpoint that returns `{ status: "ok" }`.

Run locally with `npm install && npm run dev` — the server listens on
`http://127.0.0.1:3000`.
