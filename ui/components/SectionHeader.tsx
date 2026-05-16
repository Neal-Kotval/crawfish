import { ReactNode } from "react";

/**
 * SectionHeader — emoji/icon + title (+ optional subtitle + trailing
 * status). Replaces the inline flex header repeated across OpenClaw*
 * panels and wizard steps.
 */
export function SectionHeader({
  icon,
  title,
  sub,
  status,
}: {
  icon?: ReactNode;
  title: string;
  sub?: ReactNode;
  status?: ReactNode;
}) {
  return (
    <div className="cf-section-header">
      {icon ? <span className="cf-section-header__icon">{icon}</span> : null}
      <div className="cf-col" style={{ gap: 2 }}>
        <div className="cf-section-header__title">{title}</div>
        {sub ? <div className="cf-section-header__sub">{sub}</div> : null}
      </div>
      {status ? <div style={{ marginLeft: "auto" }}>{status}</div> : null}
    </div>
  );
}
