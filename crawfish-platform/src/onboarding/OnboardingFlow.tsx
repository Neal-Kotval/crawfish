/**
 * Founder onboarding — the 21-step flow distilled to 5 logical stages.
 * Each stage is a single screen; the user can hop forward/back.
 * Based on /design/User Flow - Founder Onboarding.html.
 *
 * Stages:
 *   1. welcome      — 4 questions intake
 *   2. propose      — proposed org (ascii preview of folder + agents)
 *   3. install      — streaming install logs of agents being hired
 *   4. hired        — "your company is hired" confirmation
 *   5. handoff      — deep-link to dash with device code, or stay web
 */
import { useNavigate, useParams, Link } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";

type Stage = "welcome" | "propose" | "install" | "hired" | "handoff";
const STAGES: Stage[] = ["welcome", "propose", "install", "hired", "handoff"];

export function OnboardingFlow() {
  const { step } = useParams<{ step?: string }>();
  const navigate = useNavigate();
  const idx = Math.max(0, STAGES.indexOf((step as Stage) ?? "welcome"));
  const stage = STAGES[idx];
  const next = STAGES[idx + 1];
  const prev = STAGES[idx - 1];

  const go = (s: Stage | undefined) => s ? navigate(`/onboarding/${s}`) : navigate("/");

  return (
    <div className="cf" style={{ minHeight: "100vh", background: "var(--paper)" }}>
      {/* progress bar */}
      <div style={{
        padding: "20px 56px", borderBottom: "1px solid var(--rule)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <Link to="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 24, height: 24, borderRadius: 5,
            background: "var(--ink)", color: "var(--accent)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "var(--ff-display)", fontSize: 13, fontWeight: 700, letterSpacing: "-0.04em",
          }}>cf</div>
          <span style={{ fontWeight: 600, color: "var(--ink)" }}>Crawfish</span>
        </Link>
        <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
          Step {idx + 1} of {STAGES.length} · {stage}
        </div>
        <div style={{ width: 240, height: 4, background: "var(--paper-2)", borderRadius: 999, overflow: "hidden" }}>
          <div style={{
            width: `${((idx + 1) / STAGES.length) * 100}%`,
            height: "100%", background: "var(--accent)", transition: "width 320ms ease",
          }} />
        </div>
      </div>

      <main style={{ padding: "64px 56px", maxWidth: 920, margin: "0 auto" }}>
        {stage === "welcome" && <Welcome onNext={() => go("propose")} />}
        {stage === "propose" && <Propose onNext={() => go("install")} />}
        {stage === "install" && <Install onNext={() => go("hired")} />}
        {stage === "hired"   && <Hired   onNext={() => go("handoff")} />}
        {stage === "handoff" && <Handoff />}

        <div style={{
          marginTop: 48, paddingTop: 24, borderTop: "1px solid var(--rule)",
          display: "flex", justifyContent: "space-between",
        }}>
          <button type="button" className="cfp-btn"
            onClick={() => go(prev)}
            disabled={!prev}
            style={{ visibility: prev ? "visible" : "hidden" }}
          >← Back</button>
          <button type="button" className="cfp-btn cfp-btn--primary"
            onClick={() => go(next)}
            style={{ visibility: next ? "visible" : "hidden" }}
          >Continue →</button>
        </div>
      </main>
    </div>
  );
}

function Welcome({ onNext }: { onNext: () => void }) {
  const inputStyle: React.CSSProperties = {
    width: "100%", padding: "10px 14px", border: "1px solid var(--rule-3)",
    borderRadius: "var(--r-sm)", fontFamily: "var(--ff-sans)", fontSize: 15,
    background: "var(--surface-2)", color: "var(--ink)",
  };
  return (
    <>
      <Eyebrow>Welcome · 4 questions</Eyebrow>
      <h1 style={{
        fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 56, lineHeight: 1.02,
        letterSpacing: "-0.032em", margin: "8px 0 16px",
      }}>Let's hire your company.</h1>
      <p style={{ color: "var(--ink-soft)", fontSize: 16, maxWidth: 560, marginBottom: 32 }}>
        Four quick questions. We'll propose an org structure on the next screen, then you can change anything.
      </p>

      <div style={{ marginBottom: 18 }}>
        <Eyebrow style={{ marginBottom: 6 }}>What are you building?</Eyebrow>
        <input placeholder="e.g., a B2B SaaS analytics tool" style={inputStyle} />
      </div>

      <div style={{ marginBottom: 18 }}>
        <Eyebrow style={{ marginBottom: 6 }}>What's your team called?</Eyebrow>
        <input placeholder="e.g., acme-co" style={inputStyle} />
      </div>

      <div style={{ marginBottom: 18 }}>
        <Eyebrow style={{ marginBottom: 8 }}>How big is the team today?</Eyebrow>
        <SegRow options={["Just me", "2–5", "5–20", "20+"]} defaultIndex={0} />
      </div>

      <div style={{ marginBottom: 18 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Where do you spend most days?</Eyebrow>
        <SegRow options={["Dash", "CLI", "IDE", "All three"]} defaultIndex={0} />
      </div>
    </>
  );
}

function SegRow({ options, defaultIndex = 0 }: { options: string[]; defaultIndex?: number }) {
  return (
    <div style={{
      display: "inline-flex", padding: 3, gap: 2,
      background: "var(--paper-2)", border: "1px solid var(--rule)",
      borderRadius: "var(--r-sm)",
    }}>
      {options.map((o, i) => (
        <button key={o} type="button" style={{
          appearance: "none", cursor: "pointer", border: "none",
          padding: "6px 14px", borderRadius: 4,
          fontFamily: "var(--ff-sans)", fontSize: 13, fontWeight: 500,
          background: i === defaultIndex ? "var(--surface-2)" : "transparent",
          color: i === defaultIndex ? "var(--ink)" : "var(--ink-mute)",
          boxShadow: i === defaultIndex ? "var(--shadow-sm)" : "none",
        }}>{o}</button>
      ))}
    </div>
  );
}

function Propose({ onNext }: { onNext: () => void }) {
  return (
    <>
      <Eyebrow>Proposed org</Eyebrow>
      <h1 style={{
        fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 48, lineHeight: 1.02,
        letterSpacing: "-0.028em", margin: "8px 0 24px",
      }}>Here's what your company looks like.</h1>

      <pre className="cf-mono" style={{
        background: "var(--ink)", color: "#e9e4d0",
        padding: 24, borderRadius: "var(--r-md)", fontSize: 12.5, lineHeight: 1.7,
        overflow: "auto",
      }}>{`acme-co/
├── agents/
│   ├── eng-bot         · engineer       · claude-code
│   ├── designer-bot    · designer       · claude-api
│   ├── support-bot     · tier-1 support · cma
│   └── ops-bot         · operations     · claude-api
├── knowledge/
│   ├── api-conventions.md
│   └── runbooks/
├── policies/
│   └── default.yaml
└── crawfish.toml`}</pre>

      <p style={{ color: "var(--ink-mute)", fontSize: 13, marginTop: 16 }}>
        You can rename anything, swap runtimes, or skip an agent on the next screen.
      </p>
    </>
  );
}

function Install({ onNext }: { onNext: () => void }) {
  const lines = [
    "$ crawfish init acme-co",
    "→ writing acme-co/crawfish.toml",
    "→ hiring eng-bot (claude-code) … done",
    "→ hiring designer-bot (claude-api) … done",
    "→ hiring support-bot (cma) … done",
    "→ hiring ops-bot (claude-api) … done",
    "→ seeding knowledge/api-conventions.md",
    "→ installing policy default.yaml",
    "✓ acme-co is ready in 14s.",
  ];
  return (
    <>
      <Eyebrow>Installing…</Eyebrow>
      <h1 style={{
        fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 48, lineHeight: 1.02,
        letterSpacing: "-0.028em", margin: "8px 0 24px",
      }}>Hiring your team.</h1>

      <div style={{
        background: "var(--ink)", color: "#e9e4d0",
        padding: 24, borderRadius: "var(--r-md)", fontFamily: "var(--ff-mono)", fontSize: 13, lineHeight: 1.8,
      }}>
        {lines.map((l, i) => (
          <div key={i} style={{ opacity: i === lines.length - 1 ? 1 : 0.85 }}>{l}</div>
        ))}
      </div>
    </>
  );
}

function Hired({ onNext }: { onNext: () => void }) {
  return (
    <>
      <Eyebrow style={{ color: "var(--good)" }}>● Your company is hired</Eyebrow>
      <h1 style={{
        fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 56, lineHeight: 1.02,
        letterSpacing: "-0.032em", margin: "8px 0 16px",
      }}>You have <span style={{ color: "var(--accent)" }}>four agents</span>.</h1>
      <p style={{ color: "var(--ink-soft)", fontSize: 16, maxWidth: 560, marginBottom: 24 }}>
        They live on disk in <span className="cf-mono">~/crawfish/acme-co/</span>. Open the dash to give one a task,
        or stay here to manage them online.
      </p>

      <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
        <Pill tone="good" live>4 agents ready</Pill>
        <Pill>knowledge seeded</Pill>
        <Pill>default policy installed</Pill>
      </div>
    </>
  );
}

function Handoff() {
  return (
    <>
      <Eyebrow>Pick your client</Eyebrow>
      <h1 style={{
        fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 44, lineHeight: 1.02,
        letterSpacing: "-0.028em", margin: "8px 0 24px",
      }}>Where do you want to work today?</h1>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <a href="crawfish-dash://link?code=A4F2K9" style={{
          background: "var(--ink)", color: "#f7f3ea", borderRadius: "var(--r-lg)",
          padding: 24, display: "flex", flexDirection: "column", gap: 8,
          textDecoration: "none", border: "1px solid var(--ink)",
        }}>
          <Eyebrow style={{ color: "rgba(247,243,234,0.55)" }}>Recommended</Eyebrow>
          <div style={{ fontFamily: "var(--ff-display)", fontSize: 28, letterSpacing: "-0.025em" }}>Open in Dash →</div>
          <div style={{ fontSize: 13, opacity: 0.7 }}>The desktop studio. Best for daily work.</div>
          <div className="cf-mono" style={{ fontSize: 11, opacity: 0.55, marginTop: "auto" }}>
            device code: <span style={{ color: "var(--accent)" }}>A4F2K9</span>
          </div>
        </a>
        <a href="/orgs/acme-co/canvas" style={{
          background: "var(--surface-2)", color: "var(--ink)", borderRadius: "var(--r-lg)",
          padding: 24, display: "flex", flexDirection: "column", gap: 8,
          textDecoration: "none", border: "1px solid var(--rule-3)",
        }}>
          <Eyebrow>Online</Eyebrow>
          <div style={{ fontFamily: "var(--ff-display)", fontSize: 28, letterSpacing: "-0.025em" }}>Stay in the browser →</div>
          <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>Multiplayer canvas. Best for teams.</div>
          <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)", marginTop: "auto" }}>
            you can install Dash later from the workspace menu
          </div>
        </a>
      </div>
    </>
  );
}
