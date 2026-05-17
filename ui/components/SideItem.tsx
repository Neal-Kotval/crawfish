import type { ReactNode } from "react";

export interface SideItemProps {
  icon?: ReactNode;
  label: ReactNode;
  active?: boolean;
  badge?: ReactNode;
  sub?: boolean;
  onClick?: () => void;
  href?: string;
}

export function SideItem({ icon, label, active, badge, sub, onClick, href }: SideItemProps) {
  const cls = [
    "cfp-side",
    active ? "cfp-side--active" : "",
    sub ? "cfp-side--sub" : "",
  ].filter(Boolean).join(" ");

  const content = (
    <>
      {icon ? <span className="cfp-side__icon">{icon}</span> : null}
      <span className="cfp-side__label">{label}</span>
      {badge ? <span className="cfp-side__badge">{badge}</span> : null}
    </>
  );

  if (href) {
    return <a href={href} className={cls} onClick={onClick}>{content}</a>;
  }
  return <button type="button" className={cls} onClick={onClick}>{content}</button>;
}
