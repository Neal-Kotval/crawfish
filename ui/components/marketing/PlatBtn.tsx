import type { ReactNode } from "react";

export interface PlatBtnProps {
  children: ReactNode;
  primary?: boolean;
  dark?: boolean;
  href?: string;
  onClick?: () => void;
}

export function PlatBtn({ children, primary, dark, href, onClick }: PlatBtnProps) {
  const style: React.CSSProperties = {
    appearance: "none", cursor: "pointer",
    fontFamily: "var(--ff-sans)", fontSize: 13, fontWeight: 500,
    padding: "8px 12px", borderRadius: "var(--r-sm)",
    background: primary ? "var(--accent)" : (dark ? "#26241f" : "var(--surface-2)"),
    color: primary ? "#fff" : (dark ? "#f7f3ea" : "var(--ink)"),
    border: primary
      ? "1px solid var(--accent)"
      : (dark ? "1px solid rgba(247,243,234,0.16)" : "1px solid var(--rule-3)"),
    display: "inline-flex", alignItems: "center", gap: 6,
    textDecoration: "none",
  };
  if (href) {
    return <a href={href} style={style} onClick={onClick}>{children}</a>;
  }
  return <button type="button" style={style} onClick={onClick}>{children}</button>;
}
