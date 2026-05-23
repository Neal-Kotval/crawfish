/**
 * ProjectIssues — the synced-issues view for one project.
 *
 * Lists issues (title, state Pill, label chips, key) from GET …/issues, with a
 * "Sync now" control that triggers ingestion and refetches. For a project not
 * yet bound to a Linear team, a picker binds one (Linear must be connected
 * first). GitHub-bound projects sync immediately via the sign-in connection.
 *
 * All issue text renders as React children (auto-escaped) — no raw HTML
 * (T-20-10).
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import { formatApiError } from "@crawfish/ui/lib/formatApiError";
import {
  listIssues,
  syncProject,
  listLinearTeams,
  selectLinearTeam,
  createTask,
  type Issue,
  type LinearTeam,
} from "../lib/api";
import type { Project } from "./Projects";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; issues: Issue[] };

export function ProjectIssues({
  orgId,
  project,
  onBack,
}: {
  orgId: string;
  project: Project;
  onBack: () => void;
}) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [syncing, setSyncing] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [teams, setTeams] = useState<LinearTeam[] | null>(null);
  const [boundTeamKey, setBoundTeamKey] = useState<string | null>(project.linearTeamKey ?? null);

  const isBound = Boolean(project.githubRepo) || Boolean(project.linearTeamId) || Boolean(boundTeamKey);

  function load() {
    setState({ kind: "loading" });
    listIssues(orgId, project.id)
      .then((issues) => setState({ kind: "ok", issues }))
      .catch((e) => setState({ kind: "error", message: formatApiError(e).body }));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [orgId, project.id]);

  async function onSync() {
    setSyncing(true);
    setNotice(null);
    try {
      const result = await syncProject(orgId, project.id);
      setNotice(`Synced ${result.synced} issue${result.synced === 1 ? "" : "s"} from ${result.provider}.`);
      load();
    } catch (e) {
      setNotice(formatApiError(e).body);
    } finally {
      setSyncing(false);
    }
  }

  async function loadTeams() {
    try {
      setTeams(await listLinearTeams(orgId));
    } catch (e) {
      setNotice(formatApiError(e).body);
    }
  }

  async function bindTeam(team: LinearTeam) {
    try {
      await selectLinearTeam(orgId, { projectId: project.id, teamId: team.id, teamKey: team.key });
      setBoundTeamKey(team.key);
      setNotice(`Bound Linear team ${team.key}. Click Sync now to pull its issues.`);
    } catch (e) {
      setNotice(formatApiError(e).body);
    }
  }

  // Promote a synced issue onto the board as an authored Task (ADR-003:
  // Issue is the provider mirror; Task is the authored work item).
  async function addToBoard(issue: Issue) {
    setNotice(null);
    try {
      await createTask(orgId, project.id, { title: issue.title });
      setNotice(`Added “${issue.title}” to the board (Triage). Open the Board to work it.`);
    } catch (e) {
      setNotice(formatApiError(e).body);
    }
  }

  return (
    <main className="cfp-shell__main" style={{ padding: 28, maxWidth: 880 }}>
      <button
        type="button"
        onClick={onBack}
        className="cfp-btn cfp-btn--sm"
        style={{ cursor: "pointer", marginBottom: 12 }}
      >
        ← Projects
      </button>
      <Eyebrow>{project.name} · issues</Eyebrow>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          margin: "6px 0 8px",
        }}
      >
        <h1
          style={{
            fontFamily: "var(--ff-display)",
            fontWeight: 500,
            fontSize: 32,
            letterSpacing: "-0.025em",
            margin: 0,
          }}
        >
          Issues
        </h1>
        <button
          type="button"
          onClick={onSync}
          disabled={syncing || !isBound}
          className="cfp-btn cfp-btn--primary"
          style={{ cursor: syncing || !isBound ? "default" : "pointer" }}
          title={isBound ? "Pull issues from the connected provider" : "Bind a provider first"}
        >
          {syncing ? "Syncing…" : "Sync now"}
        </button>
      </div>
      <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)", marginBottom: 16 }}>
        {project.githubRepo
          ? `github · ${project.githubRepo}`
          : boundTeamKey
            ? `linear · ${boundTeamKey}`
            : "no provider bound"}
      </div>

      {notice && (
        <div
          style={{
            padding: "10px 14px",
            background: "var(--surface-2)",
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-md)",
            fontSize: 13,
            color: "var(--ink-soft)",
            marginBottom: 16,
          }}
        >
          {notice}
        </div>
      )}

      {/* Linear team picker — only when nothing is bound yet. */}
      {!isBound && (
        <div
          style={{
            padding: 16,
            border: "1px dashed var(--rule-3)",
            borderRadius: "var(--r-lg)",
            background: "var(--paper)",
            marginBottom: 16,
          }}
        >
          <p style={{ fontSize: 14, color: "var(--ink-soft)", marginBottom: 12 }}>
            This project isn't bound to an issue source. Bind a Linear team to sync its issues
            (Linear must be connected on the{" "}
            <Link to={`/orgs/${orgId}/connections`} style={{ color: "var(--accent)" }}>
              Connections
            </Link>{" "}
            page first).
          </p>
          {teams === null ? (
            <button type="button" onClick={loadTeams} className="cfp-btn" style={{ cursor: "pointer" }}>
              Load Linear teams
            </button>
          ) : teams.length === 0 ? (
            <span className="cf-mono" style={{ fontSize: 12, color: "var(--ink-mute)" }}>
              No teams found — is Linear connected?
            </span>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {teams.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => bindTeam(t)}
                  className="cfp-btn cfp-btn--sm"
                  style={{ cursor: "pointer" }}
                >
                  {t.key} · {t.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      <Body state={state} onAddToBoard={addToBoard} />
    </main>
  );
}

function Body({
  state,
  onAddToBoard,
}: {
  state: LoadState;
  onAddToBoard: (issue: Issue) => void;
}) {
  if (state.kind === "loading") {
    return (
      <div className="cf-mono" style={{ color: "var(--ink-mute)", fontSize: 12 }}>
        loading…
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div
        style={{
          padding: "14px 16px",
          background: "var(--warn-bg)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-md)",
          maxWidth: 640,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>Couldn't load issues</div>
        <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>{state.message}</div>
      </div>
    );
  }
  if (state.issues.length === 0) {
    return (
      <div
        style={{
          padding: 28,
          border: "1px dashed var(--rule-3)",
          borderRadius: "var(--r-lg)",
          background: "var(--paper)",
          textAlign: "center",
          color: "var(--ink-soft)",
          fontSize: 14,
        }}
      >
        No issues synced yet. Click “Sync now” to pull them from the connected provider.
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {state.issues.map((i) => (
        <IssueRow key={i.id} issue={i} onAddToBoard={onAddToBoard} />
      ))}
    </div>
  );
}

function IssueRow({ issue, onAddToBoard }: { issue: Issue; onAddToBoard: (i: Issue) => void }) {
  const [added, setAdded] = useState(false);
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "12px 16px",
        border: "1px solid var(--rule-3)",
        borderRadius: "var(--r-md)",
        background: "var(--surface-2)",
      }}
    >
      <Pill tone={issue.state === "closed" ? "ink" : "accent"}>{issue.state}</Pill>
      <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)", minWidth: 64 }}>
        {issue.externalKey}
      </span>
      <span style={{ fontSize: 14, flex: 1 }}>
        {issue.url ? (
          <a
            href={issue.url}
            target="_blank"
            rel="noreferrer"
            style={{ color: "var(--ink)", textDecoration: "none" }}
          >
            {issue.title}
          </a>
        ) : (
          issue.title
        )}
      </span>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        {issue.labels.slice(0, 4).map((l) => (
          <Pill key={l} tone="ink">
            {l}
          </Pill>
        ))}
      </div>
      {issue.assigneeExternal && (
        <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
          {issue.assigneeExternal}
        </span>
      )}
      <button
        type="button"
        onClick={() => {
          onAddToBoard(issue);
          setAdded(true);
        }}
        disabled={added}
        className="cfp-btn cfp-btn--sm"
        title="Create a board task from this issue"
        style={{ cursor: added ? "default" : "pointer", whiteSpace: "nowrap" }}
      >
        {added ? "Added ✓" : "→ Board"}
      </button>
    </div>
  );
}
