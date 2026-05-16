import { ReactNode } from "react";

type BadgeVariant =
  | "default"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "output"
  | "outline";
type BadgeSize = "sm" | "md" | "lg";

/**
 * Badge — thin wrapper over the .cf-chip family. Use this anywhere you'd
 * otherwise hand-roll a colored rounded label (live indicators, counts,
 * runtime tags). Variants map to existing chip modifier classes so the
 * palette stays consistent with the design tokens.
 */
export function Badge({
  variant = "default",
  size = "md",
  title,
  children,
}: {
  variant?: BadgeVariant;
  size?: BadgeSize;
  title?: string;
  children: ReactNode;
}) {
  const cls = [
    "cf-chip",
    variant !== "default" ? `cf-chip--${variant}` : "",
    size !== "md" ? `cf-chip--${size}` : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={cls} title={title}>
      {children}
    </span>
  );
}
