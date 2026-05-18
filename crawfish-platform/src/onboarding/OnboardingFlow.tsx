/**
 * Founder onboarding — distilled to 5 logical stages.
 *
 * MVP P2b: answer state is lifted to OnboardingFlow and the `install` stage
 * actually POSTs /api/orgs to the platform server. Streaming output is faked
 * with setTimeout for the visual feel; the API call is fast.
 *
 *   1. welcome  — 4 questions intake
 *   2. propose  — proposed org (ascii preview using the user's answers)
 *   3. install  — POST /api/orgs + streaming install logs
 *   4. hired    — "your company is hired" confirmation (real agent count)
 *   5. handoff  — deep-link to dash with device code, or stay web
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import { createOrg, type Org, type ApiError } from "../lib/api";
import { useCurrentUser } from "../lib/useAuth";

type Stage = "welcome" | "propose" | "install" | "hired" | "handoff";
const STAGES: Stage[] = ["welcome", "propose", "install", "hired", "handoff"];

type TeamSize = "Just me" | "2–5" | "5–20" | "20+";
type PrimaryClient = "Dash" | "CLI" | "IDE" | "All three";

type Answers = {
  project: string;
  name: string;
  teamSize: TeamSize;
  primaryClient: PrimaryClient;
};

const DEFAULT_AGENTS = [
  { name: "eng-bot", role: "engineer", runtime: "claude-code" },
  { name: "designer-bot", role: "designer", runtime: "claude-api" },
  { name: "support-bot", role: "tier-1 support", runtime: "cma" },
  { name: "ops-bot", role: "operations", runtime: "claude-api" },
];

const DEFAULT_ANSWERS: Answers = {
  project: "",
  name: "",
  teamSize: "Just me",
  primaryClient: "Dash",
};

export function OnboardingFlow() {
  const { step } = useParams<{ step?: string }>();
  const navigate = useNavigate();
  const idx = Math.max(0, STAGES.indexOf((step as Stage) ?? "welcome"));
  const stage = STAGES[idx];
  const next = STAGES[idx + 1];
  const prev = STAGES[idx - 1];

  const [answers, setAnswers] = useState<Answers>(DEFAULT_ANSWERS);
  const [createdOrg, setCreatedOrg] = useState<Org | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const go = (s: Stage | undefined) => (s ? navigate(`/onboarding/${s}`) : navigate("/"));

  const canContinueFromWelcome = answers.name.trim().length > 0;

  const handleContinue = async () => {
    setError(null);

    if (stage === "welcome") {
      if (!canContinueFromWelcome) {
        setError("Please give your team a name.");
        return;
      }
      // Light client-side hint; the server's regex is the source of truth.
      if (!/^[a-z0-9][a-z0-9-]*$/.test(answers.name)) {
        setError("Team name: lowercase letters, digits, and dashes only.");
        return;
      }
      go("propose");
      return;
    }

    if (stage === "propose") {
      // Kick the install: navigate first so the streaming UI renders, then
      // fire the request. The Install component below watches `submitting`
      // and `createdOrg` for state and reacts.
      go("install");
      return;
    }

    if (stage === "install") {
      // Install advances automatically when the request resolves.
      return;
    }

    if (stage === "hired") {
      go("handoff");
      return;
    }
  };

  // Drive the create request from the install stage. Runs once per install
  // visit; if it fails, we bounce back to propose with the error surfaced.
  useEffect(() => {
    if (stage !== "install") return;
    if (createdOrg) return;
    if (submitting) return;

    let cancelled = false;
    setSubmitting(true);
    (async () => {
      try {
        const org = await createOrg({
          name: answers.name,
          project: answers.project || undefined,
          teamSize: answers.teamSize,
          primaryClient: answers.primaryClient,
          // Server fills in DEFAULT_AGENTS automatically.
        });
        if (cancelled) return;
        setCreatedOrg(org);
        // Small delay so the streaming feels real even when the server is fast.
        setTimeout(() => {
          if (!cancelled) go("hired");
        }, 1400);
      } catch (e) {
        if (cancelled) return;
        const err = e as ApiError;
        setError(err.message || "Something went wrong.");
        // Bounce back so the user can fix the name.
        go("propose");
      } finally {
        if (!cancelled) setSubmitting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  return (
    <div className="cf" style={{ minHeight: "100vh", background: "var(--paper)" }}>
      <div
        style={{
          padding: "20px 56px",
          borderBottom: "1px solid var(--rule)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Link to="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 24,
              height: 24,
              borderRadius: 5,
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
            cf
          </div>
          <span style={{ fontWeight: 600, color: "var(--ink)" }}>Crawfish</span>
        </Link>
        <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
          Step {idx + 1} of {STAGES.length} · {stage}
        </div>
        <div
          style={{
            width: 240,
            height: 4,
            background: "var(--paper-2)",
            borderRadius: 999,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${((idx + 1) / STAGES.length) * 100}%`,
              height: "100%",
              background: "var(--accent)",
              transition: "width 320ms ease",
            }}
          />
        </div>
      </div>

      <main style={{ padding: "64px 56px", maxWidth: 920, margin: "0 auto" }}>
        {stage === "welcome" && (
          <Welcome answers={answers} setAnswers={setAnswers} error={error} />
        )}
        {stage === "propose" && <Propose answers={answers} error={error} />}
        {stage === "install" && <Install answers={answers} />}
        {stage === "hired" && <Hired org={createdOrg} answers={answers} />}
        {stage === "handoff" && <Handoff org={createdOrg} answers={answers} />}

        <div
          style={{
            marginTop: 48,
            paddingTop: 24,
            borderTop: "1px solid var(--rule)",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          <button
            type="button"
            className="cfp-btn"
            onClick={() => go(prev)}
            disabled={!prev || stage === "install"}
            style={{ visibility: prev && stage !== "install" ? "visible" : "hidden" }}
          >
            ← Back
          </button>
          {stage !== "install" && next ? (
            <button
              type="button"
              className="cfp-btn cfp-btn--primary"
              onClick={handleContinue}
              disabled={stage === "welcome" && !canContinueFromWelcome}
            >
              Continue →
            </button>
          ) : (
            <span />
          )}
        </div>
      </main>
    </div>
  );
}

function Welcome({
  answers,
  setAnswers,
  error,
}: {
  answers: Answers;
  setAnswers: (a: Answers) => void;
  error: string | null;
}) {
  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 14px",
    border: "1px solid var(--rule-3)",
    borderRadius: "var(--r-sm)",
    fontFamily: "var(--ff-sans)",
    fontSize: 15,
    background: "var(--surface-2)",
    color: "var(--ink)",
  };
  return (
    <>
      <Eyebrow>Welcome · 4 questions</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 56,
          lineHeight: 1.02,
          letterSpacing: "-0.032em",
          margin: "8px 0 16px",
        }}
      >
        Let's hire your company.
      </h1>
      <p style={{ color: "var(--ink-soft)", fontSize: 16, maxWidth: 560, marginBottom: 32 }}>
        Four quick questions. We'll propose an org structure on the next screen, then you can change anything.
      </p>

      <div style={{ marginBottom: 18 }}>
        <Eyebrow style={{ marginBottom: 6 }}>What are you building?</Eyebrow>
        <input
          placeholder="e.g., a B2B SaaS analytics tool"
          style={inputStyle}
          value={answers.project}
          onChange={(e) => setAnswers({ ...answers, project: e.target.value })}
        />
      </div>

      <div style={{ marginBottom: 18 }}>
        <Eyebrow style={{ marginBottom: 6 }}>What's your team called?</Eyebrow>
        <input
          placeholder="e.g., acme-co"
          style={inputStyle}
          value={answers.name}
          onChange={(e) => setAnswers({ ...answers, name: e.target.value })}
        />
        <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)", marginTop: 6 }}>
          lowercase letters, digits, and dashes only
        </div>
      </div>

      <div style={{ marginBottom: 18 }}>
        <Eyebrow style={{ marginBottom: 8 }}>How big is the team today?</Eyebrow>
        <SegRow
          options={["Just me", "2–5", "5–20", "20+"] as TeamSize[]}
          value={answers.teamSize}
          onChange={(v) => setAnswers({ ...answers, teamSize: v })}
        />
      </div>

      <div style={{ marginBottom: 18 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Where do you spend most days?</Eyebrow>
        <SegRow
          options={["Dash", "CLI", "IDE", "All three"] as PrimaryClient[]}
          value={answers.primaryClient}
          onChange={(v) => setAnswers({ ...answers, primaryClient: v })}
        />
      </div>

      {error && (
        <div
          style={{
            marginTop: 16,
            padding: "10px 14px",
            background: "var(--surface-warn, #fef3e6)",
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-sm)",
            color: "var(--bad, #a23a2a)",
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}
    </>
  );
}

function SegRow<T extends string>({
  options,
  value,
  onChange,
}: {
  options: T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div
      style={{
        display: "inline-flex",
        padding: 3,
        gap: 2,
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        borderRadius: "var(--r-sm)",
      }}
    >
      {options.map((o) => {
        const active = o === value;
        return (
          <button
            key={o}
            type="button"
            onClick={() => onChange(o)}
            style={{
              appearance: "none",
              cursor: "pointer",
              border: "none",
              padding: "6px 14px",
              borderRadius: 4,
              fontFamily: "var(--ff-sans)",
              fontSize: 13,
              fontWeight: 500,
              background: active ? "var(--surface-2)" : "transparent",
              color: active ? "var(--ink)" : "var(--ink-mute)",
              boxShadow: active ? "var(--shadow-sm)" : "none",
            }}
          >
            {o}
          </button>
        );
      })}
    </div>
  );
}

function Propose({ answers, error }: { answers: Answers; error: string | null }) {
  const name = answers.name || "your-org";
  return (
    <>
      <Eyebrow>Proposed org</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 48,
          lineHeight: 1.02,
          letterSpacing: "-0.028em",
          margin: "8px 0 24px",
        }}
      >
        Here's what {name} looks like.
      </h1>

      {answers.project && (
        <p style={{ color: "var(--ink-soft)", fontSize: 15, marginBottom: 16, maxWidth: 600 }}>
          For <span className="cf-mono">{answers.project}</span> · {answers.teamSize} ·{" "}
          {answers.primaryClient}
        </p>
      )}

      <pre
        className="cf-mono"
        style={{
          background: "var(--ink)",
          color: "#e9e4d0",
          padding: 24,
          borderRadius: "var(--r-md)",
          fontSize: 12.5,
          lineHeight: 1.7,
          overflow: "auto",
        }}
      >{`${name}/
├── agents/
${DEFAULT_AGENTS.map(
  (a, i) =>
    `│   ${i === DEFAULT_AGENTS.length - 1 ? "└──" : "├──"} ${a.name.padEnd(16)} · ${a.role.padEnd(15)} · ${a.runtime}`,
).join("\n")}
├── knowledge/
│   ├── api-conventions.md
│   └── runbooks/
├── policies/
│   └── default.yaml
└── crawfish.toml`}</pre>

      <p style={{ color: "var(--ink-mute)", fontSize: 13, marginTop: 16 }}>
        You can rename anything, swap runtimes, or skip an agent on the next screen.
      </p>

      {error && (
        <div
          style={{
            marginTop: 16,
            padding: "10px 14px",
            background: "var(--surface-warn, #fef3e6)",
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-sm)",
            color: "var(--bad, #a23a2a)",
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}
    </>
  );
}

function Install({ answers }: { answers: Answers }) {
  const name = answers.name || "your-org";
  const allLines = useMemo(
    () => [
      `$ crawfish init ${name}`,
      `→ writing ${name}/crawfish.toml`,
      ...DEFAULT_AGENTS.map((a) => `→ hiring ${a.name} (${a.runtime}) … done`),
      `→ seeding knowledge/api-conventions.md`,
      `→ installing policy default.yaml`,
      `✓ ${name} is ready.`,
    ],
    [name],
  );

  const [visible, setVisible] = useState(1);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setVisible((v) => (v < allLines.length ? v + 1 : v));
    }, 160);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [allLines.length]);

  return (
    <>
      <Eyebrow>Installing…</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 48,
          lineHeight: 1.02,
          letterSpacing: "-0.028em",
          margin: "8px 0 24px",
        }}
      >
        Hiring your team.
      </h1>

      <div
        style={{
          background: "var(--ink)",
          color: "#e9e4d0",
          padding: 24,
          borderRadius: "var(--r-md)",
          fontFamily: "var(--ff-mono)",
          fontSize: 13,
          lineHeight: 1.8,
          minHeight: 280,
        }}
      >
        {allLines.slice(0, visible).map((l, i) => (
          <div key={i} style={{ opacity: i === visible - 1 ? 1 : 0.85 }}>
            {l}
          </div>
        ))}
      </div>
    </>
  );
}

function Hired({ org, answers }: { org: Org | null; answers: Answers }) {
  const name = org?.name ?? answers.name ?? "your-org";
  const count = org?.agents.length ?? DEFAULT_AGENTS.length;
  const wordCount =
    count === 1 ? "one agent" :
    count === 2 ? "two agents" :
    count === 3 ? "three agents" :
    count === 4 ? "four agents" :
    `${count} agents`;
  return (
    <>
      <Eyebrow style={{ color: "var(--good)" }}>● Your company is hired</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 56,
          lineHeight: 1.02,
          letterSpacing: "-0.032em",
          margin: "8px 0 16px",
        }}
      >
        You have <span style={{ color: "var(--accent)" }}>{wordCount}</span>.
      </h1>
      <p style={{ color: "var(--ink-soft)", fontSize: 16, maxWidth: 560, marginBottom: 24 }}>
        They live on disk in <span className="cf-mono">~/crawfish/{name}/</span>. Open the dash to give one
        a task, or stay here to manage them online.
      </p>

      <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
        <Pill tone="good" live>
          {count} agents ready
        </Pill>
        <Pill>knowledge seeded</Pill>
        <Pill>default policy installed</Pill>
      </div>
    </>
  );
}

const MARKETING_URL = (import.meta.env.VITE_MARKETING_URL as string | undefined) ?? "http://localhost:5173";

function Handoff({ org, answers }: { org: Org | null; answers: Answers }) {
  const name = org?.name ?? answers.name ?? "your-org";
  const navigate = useNavigate();
  const me = useCurrentUser();
  const [dashLikelyMissing, setDashLikelyMissing] = useState(false);

  // Custom-scheme links fail silently in browsers when no app is registered.
  // Heuristic: after clicking, if the window doesn't lose focus within 1.5s
  // the protocol wasn't handled. Surface a download fallback inline.
  function tryOpenDash(e: React.MouseEvent<HTMLAnchorElement>) {
    e.preventDefault();
    const params = new URLSearchParams({ org: name });
    if (me.email) params.set("user", me.email);
    if (me.name) params.set("name", me.name);
    const href = `crawfish-dash://link?${params.toString()}`;
    const startedAt = Date.now();
    const onHide = () => {
      if (document.hidden) {
        window.removeEventListener("visibilitychange", onHide);
      }
    };
    window.addEventListener("visibilitychange", onHide);
    window.location.href = href;
    window.setTimeout(() => {
      window.removeEventListener("visibilitychange", onHide);
      if (!document.hidden && Date.now() - startedAt < 2000) {
        setDashLikelyMissing(true);
      }
    }, 1500);
  }

  return (
    <>
      <Eyebrow>Pick your client</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 44,
          lineHeight: 1.02,
          letterSpacing: "-0.028em",
          margin: "8px 0 24px",
        }}
      >
        Where do you want to work today?
      </h1>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <a
          href={`crawfish-dash://link?org=${encodeURIComponent(name)}${me.email ? `&user=${encodeURIComponent(me.email)}` : ""}${me.name ? `&name=${encodeURIComponent(me.name)}` : ""}`}
          onClick={tryOpenDash}
          style={{
            background: "var(--ink)",
            color: "#f7f3ea",
            borderRadius: "var(--r-lg)",
            padding: 24,
            display: "flex",
            flexDirection: "column",
            gap: 8,
            textDecoration: "none",
            border: "1px solid var(--ink)",
          }}
        >
          <Eyebrow style={{ color: "rgba(247,243,234,0.55)" }}>Recommended</Eyebrow>
          <div style={{ fontFamily: "var(--ff-display)", fontSize: 28, letterSpacing: "-0.025em" }}>
            Open in Dash →
          </div>
          <div style={{ fontSize: 13, opacity: 0.7 }}>The desktop studio. Best for daily work.</div>
          <div className="cf-mono" style={{ fontSize: 11, opacity: 0.55, marginTop: "auto" }}>
            org: <span style={{ color: "var(--accent)" }}>{name}</span>
          </div>
        </a>
        <Link
          to={`/orgs/${encodeURIComponent(name)}/canvas`}
          style={{
            background: "var(--surface-2)",
            color: "var(--ink)",
            borderRadius: "var(--r-lg)",
            padding: 24,
            display: "flex",
            flexDirection: "column",
            gap: 8,
            textDecoration: "none",
            border: "1px solid var(--rule-3)",
          }}
        >
          <Eyebrow>Online</Eyebrow>
          <div style={{ fontFamily: "var(--ff-display)", fontSize: 28, letterSpacing: "-0.025em" }}>
            Stay in the browser →
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>
            Read-only canvas today. Multiplayer coming soon.
          </div>
          <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)", marginTop: "auto" }}>
            you can install Dash later from the workspace menu
          </div>
        </Link>
      </div>

      {dashLikelyMissing ? (
        <div
          style={{
            marginTop: 16,
            padding: "14px 16px",
            border: "1px dashed var(--rule-3)",
            borderRadius: "var(--r-md)",
            background: "var(--surface-2)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 12,
          }}
        >
          <div>
            <div style={{ fontSize: 13, color: "var(--ink)" }}>
              Dash didn't open. Looks like the desktop app isn't installed yet.
            </div>
            <div style={{ fontSize: 12, color: "var(--ink-mute)", marginTop: 2 }}>
              Grab it from the marketing site, then come back and click Open in Dash.
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <a
              className="cfp-btn cfp-btn--sm"
              href={MARKETING_URL}
              target="_blank"
              rel="noopener noreferrer"
            >
              Download Dash
            </a>
            <button
              type="button"
              className="cfp-btn cfp-btn--sm"
              onClick={() => navigate(`/orgs/${encodeURIComponent(name)}/canvas`)}
            >
              Stay in browser
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
