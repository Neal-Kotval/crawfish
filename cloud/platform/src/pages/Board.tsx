/**
 * Board — the canonical cloud Task board (ADR-003).
 *
 * Org-level surface with a project picker (the board routes are project-scoped),
 * then a kanban of Tasks grouped by the canonical TaskStatus. Members can create
 * tasks and move them between statuses (writes are gated to member+ server-side;
 * a viewer's PATCH will 403 and surface as an error). A collapsible activity
 * feed shows recent board changes.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import { formatApiError } from "@crawfish/ui/lib/formatApiError";
import {
  listProjects,
  listTasks,
  createTask,
  updateTask,
  listActivity,
  streamBoard,
  TASK_STATUSES,
  type ProjectSummary,
  type Task,
  type TaskStatus,
  type Activity,
} from "../lib/api";

const STATUS_LABEL: Record<TaskStatus, string> = {
  triage: "Triage",
  backlog: "Backlog",
  in_progress: "In Progress",
  in_review: "In Review",
  blocked: "Blocked",
  done: "Done",
  canceled: "Canceled",
};

type Load =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; tasks: Task[] };

export function Board({ orgId }: { orgId: string }) {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [pid, setPid] = useState<string | null>(null);
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [activity, setActivity] = useState<Activity[]>([]);
  const [showActivity, setShowActivity] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [live, setLive] = useState(false);

  // Load projects once, default-select the first.
  useEffect(() => {
    let cancelled = false;
    listProjects(orgId)
      .then((ps) => {
        if (cancelled) return;
        setProjects(ps);
        if (ps.length > 0) setPid((cur) => cur ?? ps[0].id);
        else setState({ kind: "ok", tasks: [] });
      })
      .catch((e) => !cancelled && setState({ kind: "error", message: formatApiError(e).body }));
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  function reload(projectId: string) {
    setState({ kind: "loading" });
    Promise.all([listTasks(orgId, projectId), listActivity(orgId, projectId)])
      .then(([tasks, acts]) => {
        setState({ kind: "ok", tasks });
        setActivity(acts);
      })
      .catch((e) => setState({ kind: "error", message: formatApiError(e).body }));
  }

  // Load + subscribe to the live stream for the selected project. Any board
  // event (from this user or another) triggers a refetch.
  useEffect(() => {
    if (!pid) return;
    reload(pid);
    const ctrl = new AbortController();
    streamBoard(orgId, pid, () => reload(pid), ctrl.signal);
    setLive(true);
    return () => {
      ctrl.abort();
      setLive(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid, orgId]);

  async function onCreate() {
    if (!pid || !newTitle.trim()) return;
    setBusy(true);
    setNotice(null);
    try {
      await createTask(orgId, pid, { title: newTitle.trim() });
      setNewTitle("");
      reload(pid);
    } catch (e) {
      setNotice(formatApiError(e).body);
    } finally {
      setBusy(false);
    }
  }

  async function move(task: Task, status: TaskStatus) {
    if (!pid || status === task.status) return;
    setNotice(null);
    try {
      await updateTask(orgId, pid, task.id, { status });
      reload(pid);
    } catch (e) {
      setNotice(formatApiError(e).body); // e.g. viewer → 403 forbidden
    }
  }

  const tasks = state.kind === "ok" ? state.tasks : [];

  return (
    <main className="cfp-shell__main" style={{ padding: 28, display: "flex", flexDirection: "column", minHeight: 0 }}>
      <Eyebrow>{orgId} · board</Eyebrow>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, margin: "6px 0 16px" }}>
        <h1 style={{ fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 32, letterSpacing: "-0.025em", margin: 0 }}>
          Board
        </h1>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {live && <Pill tone="accent">● live</Pill>}
          {projects && projects.length > 0 && (
            <select
              value={pid ?? ""}
              onChange={(e) => setPid(e.target.value)}
              aria-label="Select project"
              className="cf-mono"
              style={{ fontSize: 12, padding: "6px 8px", background: "var(--surface-2)", color: "var(--ink)", border: "1px solid var(--rule-3)", borderRadius: "var(--r-md)" }}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
          <button type="button" onClick={() => setShowActivity((v) => !v)} className="cfp-btn cfp-btn--sm" style={{ cursor: "pointer" }}>
            {showActivity ? "Hide activity" : "Activity"}
          </button>
        </div>
      </div>

      {projects && projects.length === 0 && (
        <div style={{ padding: 28, border: "1px dashed var(--rule-3)", borderRadius: "var(--r-lg)", background: "var(--paper)", textAlign: "center" }}>
          <p style={{ color: "var(--ink-soft)", fontSize: 14, marginBottom: 16 }}>
            No projects yet. The board lives inside a project — add one to get started.
          </p>
          <Link to={`/orgs/${orgId}/projects`} className="cfp-btn cfp-btn--primary" style={{ textDecoration: "none" }}>
            Go to Projects →
          </Link>
        </div>
      )}

      {pid && (
        <>
          {/* New task */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && onCreate()}
              placeholder="New task title…"
              aria-label="New task title"
              style={{ flex: 1, maxWidth: 420, fontSize: 14, padding: "8px 12px", background: "var(--surface-2)", color: "var(--ink)", border: "1px solid var(--rule-3)", borderRadius: "var(--r-md)" }}
            />
            <button type="button" onClick={onCreate} disabled={busy || !newTitle.trim()} className="cfp-btn cfp-btn--primary" style={{ cursor: busy || !newTitle.trim() ? "default" : "pointer" }}>
              Add task
            </button>
          </div>

          {notice && (
            <div style={{ padding: "10px 14px", background: "var(--warn-bg)", border: "1px solid var(--rule-3)", borderRadius: "var(--r-md)", fontSize: 13, color: "var(--ink-soft)", marginBottom: 16 }}>
              {notice}
            </div>
          )}

          {state.kind === "loading" && (
            <div className="cf-mono" style={{ color: "var(--ink-mute)", fontSize: 12 }}>loading…</div>
          )}
          {state.kind === "error" && (
            <div style={{ padding: "14px 16px", background: "var(--warn-bg)", border: "1px solid var(--rule-3)", borderRadius: "var(--r-md)" }}>
              <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>Couldn't load the board</div>
              <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>{state.message}</div>
            </div>
          )}

          {state.kind === "ok" && (
            <div style={{ display: "flex", gap: 12, overflowX: "auto", paddingBottom: 8, alignItems: "flex-start" }}>
              {TASK_STATUSES.map((s) => {
                const col = tasks.filter((t) => t.status === s);
                return (
                  <div key={s} style={{ flex: "1 0 200px", minWidth: 200, display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 2px" }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)" }}>{STATUS_LABEL[s]}</span>
                      <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>{col.length}</span>
                    </div>
                    {col.map((t) => (
                      <TaskCard key={t.id} task={t} onMove={move} />
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {showActivity && (
        <div style={{ marginTop: 20, borderTop: "1px solid var(--rule)", paddingTop: 16 }}>
          <Eyebrow>activity</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
            {activity.length === 0 ? (
              <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>no activity yet</span>
            ) : (
              activity.map((a) => (
                <div key={a.id} className="cf-mono" style={{ fontSize: 11, color: "var(--ink-soft)" }}>
                  <span style={{ color: "var(--ink-mute)" }}>{new Date(a.createdAt).toLocaleString()}</span>{" "}
                  · {a.kind}
                  {a.payload && Object.keys(a.payload).length > 0 ? ` ${JSON.stringify(a.payload)}` : ""}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </main>
  );
}

function TaskCard({ task, onMove }: { task: Task; onMove: (t: Task, s: TaskStatus) => void }) {
  return (
    <div style={{ padding: 12, border: "1px solid var(--rule-3)", borderRadius: "var(--r-md)", background: "var(--surface-2)", display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 6, justifyContent: "space-between" }}>
        <span style={{ fontSize: 13 }}>{task.title}</span>
        {task.escalated && <Pill tone="danger">escalated</Pill>}
      </div>
      {/* Status lives in the column header; the select is the sole control to move it. */}
      <select
        value={task.status}
        onChange={(e) => onMove(task, e.target.value as TaskStatus)}
        aria-label="Move task"
        className="cf-mono"
        style={{ fontSize: 11, padding: "3px 6px", width: "100%", background: "var(--paper)", color: "var(--ink-soft)", border: "1px solid var(--rule-3)", borderRadius: "var(--r-sm)" }}
      >
        {TASK_STATUSES.map((s) => (
          <option key={s} value={s}>{STATUS_LABEL[s]}</option>
        ))}
      </select>
    </div>
  );
}
