/**
 * OrgSettings — the /orgs/:org/settings surface.
 *
 * Org-level settings are still being built out (name, default runtime, policy
 * presets); for now that section is a labelled placeholder. The Appearance
 * section is live: it toggles the warm-dark / warm-light theme and persists
 * the choice in localStorage via lib/theme. The theme applies to the whole
 * SPA (the <html data-theme> attribute), not just this org.
 */
import { useEffect, useState } from "react";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import { getStoredTheme, setStoredTheme, type Theme } from "../lib/theme";

const THEME_OPTIONS: { value: Theme; label: string; hint: string }[] = [
  { value: "dark", label: "Dark", hint: "Warm espresso + vermillion — the default" },
  { value: "light", label: "Light", hint: "Warm cream + vermillion" },
];

function AppearanceSection() {
  const [theme, setTheme] = useState<Theme>(getStoredTheme());

  // Stay in sync if the theme is changed elsewhere (e.g. dash in another tab
  // can't reach us, but a future titlebar toggle in this SPA could).
  useEffect(() => {
    const onChange = (e: Event) => {
      const next = (e as CustomEvent<Theme>).detail;
      if (next === "light" || next === "dark") setTheme(next);
    };
    window.addEventListener("cf-theme-change", onChange);
    return () => window.removeEventListener("cf-theme-change", onChange);
  }, []);

  const pick = (next: Theme) => {
    setTheme(next);
    setStoredTheme(next);
  };

  return (
    <section style={{ marginTop: 32 }}>
      <h2 style={{ fontSize: 15, fontWeight: 600, margin: "0 0 4px" }}>Appearance</h2>
      <p style={{ color: "var(--ink-soft)", fontSize: 13, margin: "0 0 12px", maxWidth: 560 }}>
        Choose how Crawfish looks. Your choice is saved to this browser.
      </p>
      <div role="radiogroup" aria-label="Theme" style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 420 }}>
        {THEME_OPTIONS.map((opt) => {
          const checked = theme === opt.value;
          return (
            <div
              key={opt.value}
              role="radio"
              tabIndex={0}
              aria-checked={checked}
              onClick={() => pick(opt.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  pick(opt.value);
                }
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 14px",
                borderRadius: "var(--r-md)",
                border: `1px solid ${checked ? "var(--accent)" : "var(--rule)"}`,
                background: checked ? "var(--accent-tint)" : "var(--surface-2)",
                cursor: "pointer",
              }}
            >
              <span
                aria-hidden
                style={{
                  width: 16,
                  height: 16,
                  flexShrink: 0,
                  borderRadius: "50%",
                  border: `1px solid ${checked ? "var(--accent)" : "var(--rule-3)"}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {checked && (
                  <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)" }} />
                )}
              </span>
              <span style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 14, fontWeight: 500 }}>{opt.label}</span>
                <span style={{ fontSize: 12, color: "var(--ink-mute)" }}>{opt.hint}</span>
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function OrgSettings({ org }: { org: string }) {
  return (
    <main className="cfp-shell__main" style={{ padding: 28 }}>
      <Eyebrow>{org} · settings</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 32,
          letterSpacing: "-0.025em",
          margin: "6px 0 12px",
        }}
      >
        Org settings
      </h1>
      <p style={{ color: "var(--ink-soft)", fontSize: 14, maxWidth: 640 }}>
        Name, default runtime, and policy presets. Connect issue trackers on the Connections tab.
      </p>
      <Pill tone="warn" style={{ marginTop: 16 }}>
        org config · wire later
      </Pill>

      <AppearanceSection />
    </main>
  );
}
