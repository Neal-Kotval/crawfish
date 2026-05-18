/**
 * crawfish-starter-app — minimal Express server used as the demo target repo
 * for the Crawfish MVP. The point of this file is that it does NOT yet have
 * a /healthz endpoint — the demo agent (Eng-bot) will add one when the user
 * clicks "Run demo task" in the canvas right rail.
 *
 * After the demo runs, this file should contain a `GET /healthz` route that
 * returns `{ status: "ok" }`.
 */
import express from "express";

const app = express();

app.get("/", (_req, res) => {
  res.json({ name: "crawfish-starter", version: "0.0.1" });
});

const port = Number(process.env.PORT ?? 3000);
if (process.argv[1] && process.argv[1].endsWith("server.ts")) {
  app.listen(port, () => {
    // eslint-disable-next-line no-console
    console.log(`crawfish-starter listening on http://127.0.0.1:${port}`);
  });
}

export default app;
