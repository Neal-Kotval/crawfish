import type { ReactNode } from "react";

export type PillTone = "neutral" | "accent" | "good" | "warn" | "danger" | "ink";

export interface PillProps {
  children: ReactNode;
  tone?: PillTone;
  live?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function Pill({ children, tone = "neutral", live, className, style }: PillProps) {
  const tones: Record<PillTone, string> = {
    neutral: "",
    accent: "cfp-pill--accent",
    good: "cfp-pill--good",
    warn: "cfp-pill--warn",
    danger: "cfp-pill--danger",
    ink: "cfp-pill--ink",
  };
  const cls = [
    "cfp-pill",
    tones[tone],
    live ? "cfp-pill--live" : "",
    className ?? "",
  ].filter(Boolean).join(" ");
  return <span className={cls} style={style}>{children}</span>;
}
