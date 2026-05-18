import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import { listMyOrgs, type OrgSummary, type ApiError } from "../lib/api";

export function OrgPicker() {
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState<OrgSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listMyOrgs()
      .then((data) => {
        if (!cancelled) setOrgs(data);
      })
      .catch((e) => {
        if (cancelled) return;
        const err = e as ApiError;
        setError(err.message || "Failed to load orgs.");
        setOrgs([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loading = orgs === null;
  const empty = orgs !== null && orgs.length === 0;

  return (
    <main className="cfp-shell__main" style={{ padding: 28 }}>
      <Eyebrow>Your orgs</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 36,
          letterSpacing: "-0.028em",
          margin: "8px 0 24px",
        }}
      >
        {loading ? "Loading…" : empty ? "No orgs yet" : "Pick an org"}
      </h1>

      {error && (
        <div
          className="cf-mono"
          style={{
            marginBottom: 16,
            padding: "8px 12px",
            fontSize: 12,
            color: "var(--danger)",
            background: "var(--warn-bg)",
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-sm)",
            maxWidth: 1000,
          }}
        >
          {error}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
          gap: 16,
          maxWidth: 1000,
        }}
      >
        {loading && (
          <div
            className="cf-mono"
            style={{
              padding: 24,
              color: "var(--ink-mute)",
              fontSize: 12,
              border: "1px dashed var(--rule)",
              borderRadius: "var(--r-lg)",
            }}
          >
            loading…
          </div>
        )}

        {!loading &&
          orgs!.map((o) => (
            <button
              key={o.id}
              type="button"
              onClick={() => navigate(`/orgs/${o.name}/canvas`)}
              style={{
                appearance: "none",
                cursor: "pointer",
                textAlign: "left",
                background: "var(--surface-2)",
                border: "1px solid var(--rule-3)",
                borderRadius: "var(--r-lg)",
                padding: 18,
                display: "flex",
                flexDirection: "column",
                gap: 10,
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 6,
                      background: "var(--ink)",
                      color: "var(--accent)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: "var(--ff-display)",
                      fontSize: 13,
                      fontWeight: 700,
                      letterSpacing: "-0.04em",
                    }}
                  >
                    {o.name.slice(0, 2)}
                  </div>
                  <div
                    style={{
                      fontFamily: "var(--ff-display)",
                      fontWeight: 500,
                      fontSize: 22,
                      letterSpacing: "-0.018em",
                    }}
                  >
                    {o.name}
                  </div>
                </div>
                <Pill tone="ink">{o.role}</Pill>
              </div>
              <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
                {o.memberCount} member{o.memberCount === 1 ? "" : "s"} · {o.agentCount} agent
                {o.agentCount === 1 ? "" : "s"}
                {o.project ? ` · ${o.project}` : ""}
              </div>
            </button>
          ))}

        <button
          type="button"
          onClick={() => navigate("/onboarding")}
          style={{
            appearance: "none",
            cursor: "pointer",
            background: empty ? "var(--surface-2)" : "transparent",
            border: empty ? "1px solid var(--rule-3)" : "1px dashed var(--rule-3)",
            borderRadius: "var(--r-lg)",
            padding: 18,
            minHeight: 100,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            color: empty ? "var(--ink)" : "var(--ink-mute)",
            fontSize: empty ? 16 : 14,
            fontWeight: empty ? 500 : 400,
            boxShadow: empty ? "var(--shadow-sm)" : "none",
          }}
        >
          {empty ? "Start onboarding →" : "+ Create a new org"}
        </button>
      </div>
    </main>
  );
}
