import { ReactNode } from "react";

type Tone = "blue" | "cyan" | "violet" | "mint" | "amber" | "pink" | "slate";
type Size = "sm" | "md" | "lg";

/**
 * IconDisc — colorful rounded badge wrapping an icon. Used at the start
 * of list items, KPI tiles, and suggestion cards to give the surface
 * pre-attentive color without painting whole regions.
 */
export function IconDisc({
  icon,
  tone = "blue",
  size = "md",
}: {
  icon: ReactNode;
  tone?: Tone;
  size?: Size;
}) {
  const cls = [
    "cf-icon-disc",
    `cf-icon-disc--${tone}`,
    size !== "md" ? `cf-icon-disc--${size}` : "",
  ]
    .filter(Boolean)
    .join(" ");
  return <span className={cls}>{icon}</span>;
}
