import { CSSProperties, HTMLAttributes, ReactNode } from "react";

type Tone = "default" | "soft" | "strong";

export interface GlassPanelProps extends HTMLAttributes<HTMLDivElement> {
  tone?: Tone;
  /** Renders the panel as a sticky header strip (uses .cf-glass-bar). */
  bar?: boolean;
  children?: ReactNode;
  style?: CSSProperties;
}

/**
 * Frosted-glass surface. Reserve for floating chrome: sticky route
 * headers, command palettes, modal headers, side drawers, tooltips.
 * Falls back to a solid elevated surface where backdrop-filter is
 * unavailable.
 */
export function GlassPanel({ tone = "default", bar, className, children, ...rest }: GlassPanelProps) {
  const base = bar ? "cf-glass-bar" : "cf-glass";
  const cls = [
    base,
    !bar && tone === "soft" ? "cf-glass--soft" : "",
    !bar && tone === "strong" ? "cf-glass--strong" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={cls} {...rest}>
      {children}
    </div>
  );
}
