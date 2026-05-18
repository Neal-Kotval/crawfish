import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import {
  listMyOrgs,
  listProjects,
  type OrgSummary,
  type ProjectSummary,
} from "../lib/api";
import { formatApiError } from "@crawfish/ui/lib/formatApiError";
import { ImportModal } from "./ImportModal";

type ProjectsState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; projects: ProjectSummary[] }
  | { kind: "error"; title: string; body: string };

type Importer = { orgId: string; orgName: string; tab: "create" | "local" | "github" } | null;

export function OrgPicker() {
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState<OrgSummary[] | null>(null);
  const [error, setError] = useState<{ title: string; body: string } | null>(null);
  const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
  const [projectsByOrg, setProjectsByOrg] = useState<Record<string, ProjectsState>>({});
  const [importer, setImporter] = useState<Importer>(null);

  useEffect(() => {
    let cancelled = false;
    listMyOrgs()
      .then((data) => {
        if (cancelled) return;
        setOrgs(data);
        // Auto-select the first org so the Projects panel has content on first paint.
        if (data.length > 0) setSelectedOrgId(data[0].id);
      })
      .catch((e) => {
        if (cancelled) return;
        const friendly = formatApiError(e);
        setError({ title: friendly.title, body: friendly.body });
        setOrgs([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedOrgId && !projectsByOrg[selectedOrgId]) {
      void loadProjects(selectedOrgId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgId]);

  async function loadProjects(orgId: string) {
    setProjectsByOrg((prev) => ({ ...prev, [orgId]: { kind: "loading" } }));
    try {
      const projects = await listProjects(orgId);
      setProjectsByOrg((prev) => ({ ...prev, [orgId]: { kind: "ok", projects } }));
    } catch (e) {
      const friendly = formatApiError(e);
      setProjectsByOrg((prev) => ({
        ...prev,
        [orgId]: { kind: "error", title: friendly.title, body: friendly.body },
      }));
    }
  }

  function openImporter(tab: "create" | "local" | "github") {
    const org = orgs?.find((o) => o.id === selectedOrgId);
    if (!org) return;
    setImporter({ orgId: org.id, orgName: org.name, tab });
  }

  const loading = orgs === null;
  const empty = orgs !== null && orgs.length === 0;
  const selectedOrg = orgs?.find((o) => o.id === selectedOrgId) ?? null;
  const projectsState = selectedOrg ? projectsByOrg[selectedOrg.id] : undefined;

  return (
    <main className="cfp-shell__main" style={{ padding: 28 }}>
      <Eyebrow>Workspace</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 36,
          letterSpacing: "-0.028em",
          margin: "8px 0 24px",
        }}
      >
        {loading ? "Loading…" : empty ? "No orgs yet" : "Pick an org or project"}
      </h1>

      {error && (
        <div
          style={{
            marginBottom: 24,
            padding: "14px 16px",
            background: "var(--warn-bg)",
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-md)",
            maxWidth: 1100,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)", marginBottom: 4 }}>
            {error.title}
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>{error.body}</div>
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 380px) minmax(0, 1fr)",
          gap: 24,
          maxWidth: 1100,
          alignItems: "start",
        }}
        data-layout="two-panel"
      >
        {/* ── Orgs panel ───────────────────────────────────────── */}
        <section
          aria-labelledby="orgs-heading"
          style={{ display: "flex", flexDirection: "column", gap: 10 }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
            }}
          >
            <h2
              id="orgs-heading"
              style={{
                fontFamily: "var(--ff-display)",
                fontWeight: 500,
                fontSize: 18,
                letterSpacing: "-0.018em",
                margin: 0,
                color: "var(--ink)",
              }}
            >
              Orgs
            </h2>
            <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
              {loading ? "…" : `${orgs!.length}`}
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {loading &&
              [0, 1, 2].map((i) => (
                <div
                  key={i}
                  style={{
                    height: 64,
                    border: "1px dashed var(--rule)",
                    borderRadius: "var(--r-md)",
                    background: "var(--paper-2)",
                  }}
                />
              ))}

            {!loading &&
              orgs!.map((o) => (
                <OrgRow
                  key={o.id}
                  org={o}
                  selected={o.id === selectedOrgId}
                  onSelect={() => setSelectedOrgId(o.id)}
                  onEnter={() => navigate(`/orgs/${o.name}/canvas`)}
                />
              ))}

            <button
              type="button"
              onClick={() => navigate("/onboarding")}
              className="cf-touch-target"
              style={{
                appearance: "none",
                cursor: "pointer",
                background: empty ? "var(--surface-2)" : "transparent",
                border: empty ? "1px solid var(--rule-3)" : "1px dashed var(--rule-3)",
                borderRadius: "var(--r-md)",
                padding: "12px 14px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                color: empty ? "var(--ink)" : "var(--ink-mute)",
                fontSize: empty ? 15 : 13,
                fontWeight: empty ? 500 : 400,
                boxShadow: empty ? "var(--shadow-sm)" : "none",
              }}
            >
              {empty ? "Start onboarding →" : "+ New org"}
            </button>
          </div>
        </section>

        {/* ── Projects panel ───────────────────────────────────── */}
        <section
          aria-labelledby="projects-heading"
          style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            <h2
              id="projects-heading"
              style={{
                fontFamily: "var(--ff-display)",
                fontWeight: 500,
                fontSize: 18,
                letterSpacing: "-0.018em",
                margin: 0,
                color: "var(--ink)",
              }}
            >
              Projects{selectedOrg ? ` · ${selectedOrg.name}` : ""}
            </h2>
            {projectsState?.kind === "ok" && (
              <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
                {projectsState.projects.length}
              </span>
            )}
          </div>

          {!selectedOrg && !loading && (
            <div
              style={{
                padding: "20px 16px",
                border: "1px dashed var(--rule-3)",
                borderRadius: "var(--r-md)",
                color: "var(--ink-mute)",
                fontSize: 13,
                textAlign: "center",
              }}
            >
              Pick an org on the left to see its projects.
            </div>
          )}

          {selectedOrg && (
            <>
              <ProjectList
                state={projectsState}
                onPick={(p) =>
                  navigate(`/orgs/${selectedOrg.name}/projects?selected=${encodeURIComponent(p.id)}`)
                }
              />

              <div
                style={{
                  marginTop: 4,
                  padding: 14,
                  background: "var(--surface)",
                  border: "1px solid var(--rule)",
                  borderRadius: "var(--r-md)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 10,
                }}
              >
                <Eyebrow>Add a project</Eyebrow>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  <CreateButton onClick={() => openImporter("create")} primary>
                    + Create locally
                  </CreateButton>
                  <CreateButton onClick={() => openImporter("local")}>
                    + Import locally
                  </CreateButton>
                  <CreateButton onClick={() => openImporter("github")}>
                    + Import from GitHub
                  </CreateButton>
                </div>
                <p
                  style={{
                    margin: 0,
                    fontSize: 12,
                    color: "var(--ink-mute)",
                    lineHeight: 1.5,
                  }}
                >
                  <span style={{ fontWeight: 500, color: "var(--ink-soft)" }}>Create</span> spins
                  up a fresh local folder via Dash · <span style={{ fontWeight: 500, color: "var(--ink-soft)" }}>Import locally</span> adopts an existing folder · <span style={{ fontWeight: 500, color: "var(--ink-soft)" }}>From GitHub</span> clones a repo into the org.
                </p>
              </div>
            </>
          )}
        </section>
      </div>

      {importer && (
        <ImportModal
          orgId={importer.orgId}
          orgName={importer.orgName}
          defaultTab={importer.tab}
          onClose={() => setImporter(null)}
          onCreated={() => {
            void loadProjects(importer.orgId);
            setImporter(null);
          }}
        />
      )}
    </main>
  );
}

function OrgRow({
  org,
  selected,
  onSelect,
  onEnter,
}: {
  org: OrgSummary;
  selected: boolean;
  onSelect: () => void;
  onEnter: () => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "stretch",
        gap: 6,
      }}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className="cf-touch-target"
        style={{
          appearance: "none",
          cursor: "pointer",
          flex: 1,
          textAlign: "left",
          background: selected ? "var(--accent-tint)" : "var(--surface-2)",
          border: `1px solid ${selected ? "var(--accent-soft)" : "var(--rule-3)"}`,
          borderRadius: "var(--r-md)",
          padding: "10px 12px",
          display: "flex",
          alignItems: "center",
          gap: 10,
          minWidth: 0,
        }}
      >
        <span
          aria-hidden="true"
          style={{
            width: 30,
            height: 30,
            borderRadius: 6,
            background: "var(--ink)",
            color: "var(--accent)",
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "var(--ff-display)",
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: "-0.04em",
            flexShrink: 0,
          }}
        >
          {org.name.slice(0, 2)}
        </span>
        <span
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 1,
            minWidth: 0,
            flex: 1,
          }}
        >
          <span
            style={{
              fontFamily: "var(--ff-display)",
              fontWeight: 500,
              fontSize: 16,
              letterSpacing: "-0.014em",
              color: "var(--ink)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {org.name}
          </span>
          <span className="cf-mono" style={{ fontSize: 10, color: "var(--ink-mute)" }}>
            {org.memberCount}m · {org.agentCount}a · {org.role}
          </span>
        </span>
      </button>
      <button
        type="button"
        onClick={onEnter}
        aria-label={`Open ${org.name} canvas`}
        className="cf-touch-target"
        title="Open canvas"
        style={{
          appearance: "none",
          cursor: "pointer",
          width: 44,
          background: "var(--surface)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-md)",
          color: "var(--ink-soft)",
          fontSize: 16,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        →
      </button>
    </div>
  );
}

function ProjectList({
  state,
  onPick,
}: {
  state: ProjectsState | undefined;
  onPick: (p: ProjectSummary) => void;
}) {
  if (!state || state.kind === "idle" || state.kind === "loading") {
    return (
      <div
        style={{
          padding: "12px 14px",
          fontSize: 12,
          fontFamily: "var(--ff-mono)",
          color: "var(--ink-mute)",
          border: "1px dashed var(--rule)",
          borderRadius: "var(--r-md)",
        }}
      >
        loading…
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div
        style={{
          padding: "12px 14px",
          background: "var(--warn-bg)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-md)",
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", marginBottom: 2 }}>
          {state.title}
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{state.body}</div>
      </div>
    );
  }
  if (state.projects.length === 0) {
    return (
      <div
        style={{
          padding: "16px",
          fontSize: 13,
          color: "var(--ink-mute)",
          border: "1px dashed var(--rule)",
          borderRadius: "var(--r-md)",
          textAlign: "center",
        }}
      >
        No projects yet. Add one below to get started.
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {state.projects.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onPick(p)}
          className="cf-touch-target"
          style={{
            appearance: "none",
            cursor: "pointer",
            background: "var(--surface-2)",
            border: "1px solid var(--rule)",
            borderRadius: "var(--r-md)",
            padding: "10px 12px",
            textAlign: "left",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <span style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>{p.name}</span>
            <span
              className="cf-mono"
              style={{
                fontSize: 11,
                color: "var(--ink-mute)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {p.githubRepo ?? p.localPath ?? "—"}
            </span>
          </span>
          <Pill tone={p.cloneStatus === "cloned" ? "good" : "ink"}>
            {projectStatusLabel(p)}
          </Pill>
        </button>
      ))}
    </div>
  );
}

function projectStatusLabel(p: ProjectSummary): string {
  if (p.cloneStatus === "local_only") return "local";
  if (p.cloneStatus === "cloning") return "cloning…";
  if (p.cloneStatus === "cloned") return "cloned";
  return "error";
}

function CreateButton({
  onClick,
  primary,
  children,
}: {
  onClick: () => void;
  primary?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="cf-touch-target"
      style={{
        appearance: "none",
        cursor: "pointer",
        fontFamily: "var(--ff-sans)",
        fontSize: 13,
        fontWeight: 500,
        padding: "10px 14px",
        borderRadius: "var(--r-sm)",
        background: primary ? "var(--accent)" : "var(--surface-2)",
        color: primary ? "#fff" : "var(--ink)",
        border: `1px solid ${primary ? "var(--accent)" : "var(--rule-3)"}`,
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      {children}
    </button>
  );
}
