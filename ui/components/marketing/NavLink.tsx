import type { ReactNode } from "react";

export interface NavLinkProps {
  href: string;
  children: ReactNode;
  active?: boolean;
}

export function NavLink({ href, children, active }: NavLinkProps) {
  return (
    <a
      href={href}
      className="cf-navlink cf-touch-target"
      style={{
        fontSize: 14, fontWeight: 500, letterSpacing: "-0.005em",
        color: active ? "var(--ink)" : "var(--ink-mute)",
        textDecoration: "none",
        padding: "11px 4px",
        borderBottom: active ? "1.5px solid var(--ink)" : "1.5px solid transparent",
        display: "inline-flex", alignItems: "center",
      }}
    >{children}</a>
  );
}
