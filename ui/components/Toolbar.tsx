import { ReactNode } from "react";

/**
 * Toolbar — page-level action row. Title on the left, optional subtitle,
 * action cluster on the right. Compose with <GlassPanel bar> when the
 * toolbar should float over scrolling content.
 */
export function Toolbar({
  title,
  sub,
  leading,
  actions,
  className,
}: {
  title?: ReactNode;
  sub?: ReactNode;
  leading?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={["cf-toolbar", className ?? ""].filter(Boolean).join(" ")}>
      {leading}
      <div className="cf-toolbar__title cf-truncate">
        {title}
        {sub ? <span className="cf-toolbar__sub">· {sub}</span> : null}
      </div>
      {actions ? <div className="cf-row cf-gap-2">{actions}</div> : null}
    </div>
  );
}

/**
 * PageHeader — large top-of-content heading paired with description and
 * optional action cluster. One per route, max.
 */
export function PageHeader({
  eyebrow,
  title,
  sub,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="cf-page-header">
      <div>
        {eyebrow ? <div className="cf-eyebrow" style={{ marginBottom: 8 }}>{eyebrow}</div> : null}
        <h1 className="cf-page-header__title">{title}</h1>
        {sub ? <div className="cf-page-header__sub">{sub}</div> : null}
      </div>
      {actions ? <div className="cf-page-header__actions">{actions}</div> : null}
    </div>
  );
}
