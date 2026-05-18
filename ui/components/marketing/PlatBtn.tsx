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
    padding: "10px 14px", borderRadius: "var(--r-sm)",
    background: primary ? "var(--accent)" : (dark ? "var(--ink)" : "var(--surface-2)"),
    color: primary ? "#fff" : (dark ? "var(--ink-on)" : "var(--ink)"),
    border: primary
      ? "1px solid var(--accent)"
      : (dark ? "1px solid rgba(233,228,208,0.16)" : "1px solid var(--rule-3)"),
    display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
    textDecoration: "none",
  };
  const className = "cf-platbtn cf-touch-target";
  if (href) {
    return <a href={href} className={className} style={style} onClick={onClick}>{children}</a>;
  }
  return <button type="button" className={className} style={style} onClick={onClick}>{children}</button>;
}
