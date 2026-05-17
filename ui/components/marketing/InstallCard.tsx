import type { ReactNode } from "react";

export interface InstallCardProps {
  tag?: ReactNode;
  eyebrow: ReactNode;
  title: ReactNode;
  blurb: ReactNode;
  cta: ReactNode;
  foot?: ReactNode;
  highlight?: boolean;
}

export function InstallCard({
  tag, eyebrow, title, blurb, cta, foot, highlight,
}: InstallCardProps) {
  return (
    <div
      style={{
        background: highlight ? "var(--ink)" : "var(--surface-2)",
        color: highlight ? "#f7f3ea" : "var(--ink)",
        border: highlight ? "1px solid var(--ink)" : "1px solid var(--rule-3)",
        borderRadius: "var(--r-lg)",
        padding: "24px 24px 22px",
        display: "flex", flexDirection: "column", gap: 14,
        position: "relative", minHeight: 320,
        boxShadow: highlight ? "var(--shadow-md)" : "var(--shadow-sm)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="cf-eyebrow" style={{ color: highlight ? "rgba(247,243,234,0.55)" : "var(--ink-mute)" }}>
          {eyebrow}
        </span>
        {tag ? (
          <span style={{
            fontSize: 10, fontFamily: "var(--ff-mono)", letterSpacing: "0.08em", textTransform: "uppercase",
            padding: "3px 8px", borderRadius: 999,
            background: highlight ? "var(--accent)" : "var(--accent-tint)",
            color: highlight ? "#fff" : "var(--accent)",
            border: highlight ? "none" : "1px solid var(--accent-soft)",
          }}>{tag}</span>
        ) : null}
      </div>

      <div>
        <div style={{
          fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 36, lineHeight: 0.98,
          letterSpacing: "-0.028em", marginBottom: 6,
        }}>{title}</div>
        <div style={{
          fontSize: 14, lineHeight: 1.5,
          color: highlight ? "rgba(247,243,234,0.7)" : "var(--ink-soft)",
          maxWidth: 260,
        }}>{blurb}</div>
      </div>

      <div style={{ flex: 1 }} />
      {cta}

      {foot ? (
        <div style={{
          fontFamily: "var(--ff-mono)", fontSize: 11,
          color: highlight ? "rgba(247,243,234,0.55)" : "var(--ink-mute)",
          paddingTop: 12,
          borderTop: highlight ? "1px solid rgba(247,243,234,0.12)" : "1px solid var(--rule)",
          display: "flex", justifyContent: "space-between",
        }}>{foot}</div>
      ) : null}
    </div>
  );
}
