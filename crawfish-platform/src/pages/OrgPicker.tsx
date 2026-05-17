import { useNavigate } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";

const ORGS = [
  { id: "acme-co",     name: "acme-co",     role: "founder",     members: 5, agents: 4, status: "live" as const },
  { id: "pat-side",    name: "pat-side",    role: "contributor", members: 2, agents: 1, status: "idle" as const },
];

export function OrgPicker() {
  const navigate = useNavigate();
  return (
    <main className="cfp-shell__main" style={{ padding: 28 }}>
      <Eyebrow>Your orgs</Eyebrow>
      <h1 style={{
        fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 36,
        letterSpacing: "-0.028em", margin: "8px 0 24px",
      }}>Pick an org</h1>

      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16,
        maxWidth: 1000,
      }}>
        {ORGS.map((o) => (
          <button
            key={o.id}
            type="button"
            onClick={() => navigate(`/orgs/${o.id}/canvas`)}
            style={{
              appearance: "none", cursor: "pointer", textAlign: "left",
              background: "var(--surface-2)", border: "1px solid var(--rule-3)",
              borderRadius: "var(--r-lg)", padding: 18,
              display: "flex", flexDirection: "column", gap: 10,
              boxShadow: "var(--shadow-sm)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{
                  width: 28, height: 28, borderRadius: 6,
                  background: "var(--ink)", color: "var(--accent)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontFamily: "var(--ff-display)", fontSize: 13, fontWeight: 700, letterSpacing: "-0.04em",
                }}>{o.name.slice(0, 2)}</div>
                <div style={{
                  fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 22,
                  letterSpacing: "-0.018em",
                }}>{o.name}</div>
              </div>
              <Pill tone={o.status === "live" ? "ink" : "neutral"} live={o.status === "live"}>{o.status}</Pill>
            </div>
            <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
              {o.role} · {o.members} members · {o.agents} agents
            </div>
          </button>
        ))}

        <button type="button"
          onClick={() => navigate("/onboarding")}
          style={{
            appearance: "none", cursor: "pointer",
            background: "transparent", border: "1px dashed var(--rule-3)",
            borderRadius: "var(--r-lg)", padding: 18, minHeight: 100,
            display: "flex", alignItems: "center", justifyContent: "center",
            gap: 8, color: "var(--ink-mute)", fontSize: 14,
          }}
        >+ Create a new org</button>
      </div>
    </main>
  );
}
