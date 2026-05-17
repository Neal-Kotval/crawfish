/**
 * crawfish.dev front door.
 * Port of /design/designs/WebInstall.jsx, refactored to use the
 * @crawfish/ui marketing primitives.
 */
import { NavLink } from "@crawfish/ui/components/marketing/NavLink";
import { InstallCard } from "@crawfish/ui/components/marketing/InstallCard";
import { PlatBtn } from "@crawfish/ui/components/marketing/PlatBtn";
import {
  assetUrlFor,
  detectPlatform,
  PLATFORM_LABELS,
  RELEASES_FALLBACK_URL,
  useLatestRelease,
  type Platform,
} from "../lib/downloads";

const ALL_PLATFORMS: Exclude<Platform, "unknown">[] = ["mac-arm", "mac-intel", "linux", "windows"];

export function Index() {
  const detected = detectPlatform();
  const { release } = useLatestRelease();
  const primaryPlatform: Exclude<Platform, "unknown"> = detected === "unknown" ? "mac-arm" : detected;
  const secondaryPlatforms = ALL_PLATFORMS.filter((p) => p !== primaryPlatform);
  const urlFor = (p: Platform): string => (release ? assetUrlFor(release, p) : RELEASES_FALLBACK_URL);

  return (
    <div className="cf" style={{
      minHeight: "100vh", background: "var(--paper)", position: "relative", overflow: "hidden",
    }}>
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 1, background: "var(--accent)" }} />

      {/* nav */}
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "22px 56px", borderBottom: "1px solid var(--rule)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 6,
            background: "var(--ink)", color: "var(--accent)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "var(--ff-display)", fontSize: 16, lineHeight: 1, fontWeight: 700, letterSpacing: "-0.04em",
          }}>cf</div>
          <span style={{ fontWeight: 600, letterSpacing: "-0.012em", fontSize: 17 }}>Crawfish</span>
          <span style={{
            fontFamily: "var(--ff-mono)", fontSize: 10, letterSpacing: "0.08em",
            color: "var(--ink-mute)", padding: "2px 6px",
            border: "1px solid var(--rule-3)", borderRadius: 999, marginLeft: 4,
          }}>v0.4 · public beta</span>
        </div>
        <nav style={{ display: "flex", gap: 28 }}>
          <NavLink href="https://github.com/crawfish">Github</NavLink>
        </nav>
        <div style={{ width: 1 }} />
      </header>

      {/* hero */}
      <section style={{
        padding: "64px 56px 28px",
        display: "grid", gridTemplateColumns: "1.05fr 0.95fr", gap: 64, alignItems: "flex-end",
      }}>
        <div>
          <div className="cf-eyebrow" style={{ marginBottom: 18 }}>
            <span style={{ color: "var(--accent)", marginRight: 8 }}>●</span>
            For the founder spinning up their first five agents
          </div>
          <h1 style={{
            fontFamily: "var(--ff-display)", fontWeight: 500,
            fontSize: 76, lineHeight: 0.98, letterSpacing: "-0.035em",
            margin: 0, maxWidth: 720,
          }}>
            Hire your<br />
            company in<br />
            <span style={{ color: "var(--accent)" }}>fifteen minutes.</span>
          </h1>
          <p style={{
            fontSize: 18, lineHeight: 1.5, color: "var(--ink-soft)",
            maxWidth: 520, marginTop: 28, marginBottom: 0, letterSpacing: "-0.005em",
          }}>
            Crawfish is the operating system for companies that run on AI agents.
            One template, five working agents, one place to look. Local-first.
            MIT. No card required.
          </p>
        </div>

        <aside style={{
          fontFamily: "var(--ff-mono)", fontSize: 12, color: "var(--ink-mute)",
          background: "var(--surface)", border: "1px solid var(--rule)", borderRadius: "var(--r-lg)",
          padding: "20px 22px",
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px 28px",
          alignSelf: "end",
        }}>
          {[
            { n: "10,412", l: "weekly active orgs" },
            { n: "−35%",   l: "median compounding factor, day 30" },
            { n: "3.25×",  l: "token reduction · codebase optimizer" },
            { n: "$0",     l: "price through stage 1" },
          ].map((r) => (
            <div key={r.l}>
              <div style={{
                fontFamily: "var(--ff-sans)", fontSize: 28, color: "var(--ink)",
                fontWeight: 500, letterSpacing: "-0.01em",
              }}>{r.n}</div>
              <div>{r.l}</div>
            </div>
          ))}
        </aside>
      </section>

      {/* install picker */}
      <section style={{ padding: "40px 56px 0", display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
          <div>
            <div className="cf-eyebrow" style={{ marginBottom: 8 }}>Pick your client</div>
            <h2 style={{
              fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 34, lineHeight: 1.02,
              letterSpacing: "-0.028em", margin: 0,
            }}>How would you like to work?</h2>
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-mute)", maxWidth: 320, textAlign: "right", lineHeight: 1.5 }}>
            You can install all three later. Pick the one that matches your day. Each one talks to the same org folder on disk.
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1.05fr 1fr 1fr", gap: 16 }}>
          <InstallCard
            highlight
            tag="recommended"
            eyebrow="Desktop · Tauri"
            title={<>Dash<span style={{ color: "var(--accent)" }}>.</span></>}
            blurb="The studio. Visual org canvas, agent canvas, board, sessions, knowledge. The whole company on one screen."
            cta={
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                <PlatBtn primary href={urlFor(primaryPlatform)}>
                  {`↓ Download for ${PLATFORM_LABELS[primaryPlatform]}`}
                </PlatBtn>
                {secondaryPlatforms.map((p) => (
                  <PlatBtn key={p} dark href={urlFor(p)}>
                    {PLATFORM_LABELS[p].replace(/^Mac \(([^)]+)\)$/, "$1")}
                  </PlatBtn>
                ))}
              </div>
            }
            foot={<><span>114 MB · v0.4.1</span><span>signed · notarized</span></>}
          />
          <InstallCard
            eyebrow="Terminal · Brew · npm"
            title={<>CLI<span style={{ color: "var(--accent)" }}>.</span></>}
            blurb="Same engine, no GUI. ASCII TUI, scriptable from CI, ships the orgctl MCP server."
            cta={
              <div style={{
                background: "#1a1a18", color: "#e9e4d0",
                fontFamily: "var(--ff-mono)", fontSize: 12.5, lineHeight: 1.7,
                padding: "12px 14px", borderRadius: "var(--r-md)",
              }}>
                <div><span style={{ color: "#6fb98f" }}>$</span> brew install crawfish</div>
                <div><span style={{ color: "#6fb98f" }}>$</span> crawfish login</div>
                <div style={{ color: "#7a766c" }}># or: curl -fsSL crawfish.dev/i | sh</div>
              </div>
            }
            foot={<><span>macOS · Linux · Windows (WSL)</span><span>v0.4.1</span></>}
          />
          <InstallCard
            tag="new"
            eyebrow="Editor plugin"
            title={<>IDE<span style={{ color: "var(--accent)" }}>.</span></>}
            blurb="Sidebar inside VS Code & Cursor. Token meter in the status bar, PreToolUse policy as inline diagnostics."
            cta={
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <PlatBtn>Open VS Code marketplace ↗</PlatBtn>
                <PlatBtn>Open Cursor marketplace ↗</PlatBtn>
                <div style={{ fontSize: 12, color: "var(--ink-mute)" }}>JetBrains coming Q3 · vote on the roadmap.</div>
              </div>
            }
            foot={<><span>v0.3 · 24k installs</span><span>OSS · MIT</span></>}
          />
        </div>

        <div style={{
          marginTop: 18,
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "14px 18px",
          background: "var(--surface)", border: "1px dashed var(--rule-3)", borderRadius: "var(--r-md)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 13, color: "var(--ink-soft)" }}>
            <span>After install, your client runs locally. Your org lives in <span className="cf-mono" style={{ color: "var(--ink)" }}>~/crawfish/&lt;org&gt;/</span>.</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <span style={{ fontSize: 13, color: "var(--ink-mute)" }}>or invite the rest of your team</span>
            <a href="https://app.crawfish.dev/onboarding/team" style={{
              fontFamily: "var(--ff-sans)", fontSize: 13, fontWeight: 500,
              padding: "6px 12px", borderRadius: "var(--r-sm)",
              background: "transparent", border: "1px solid var(--ink)",
              color: "var(--ink)", textDecoration: "none",
            }}>Invite a teammate later →</a>
          </div>
        </div>
      </section>

      <footer style={{
        marginTop: 80, padding: "28px 56px",
        borderTop: "1px solid var(--rule)",
        display: "flex", justifyContent: "space-between",
        fontFamily: "var(--ff-mono)", fontSize: 11, color: "var(--ink-mute)",
      }}>
        <div>© 2026 · Crawfish · MIT</div>
        <div>made in New Orleans · status: <span style={{ color: "var(--good)" }}>● all systems</span></div>
      </footer>
    </div>
  );
}
