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
      style={{
        fontSize: 14, fontWeight: 500, letterSpacing: "-0.005em",
        color: active ? "var(--ink)" : "var(--ink-mute)",
        textDecoration: "none",
        padding: "6px 0",
        borderBottom: active ? "1.5px solid var(--ink)" : "1.5px solid transparent",
      }}
    >{children}</a>
  );
}
