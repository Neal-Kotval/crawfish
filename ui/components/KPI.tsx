import { ReactNode } from "react";

type Tone = "blue" | "violet" | "mint" | "cyan" | "amber" | "pink" | undefined;
type TrendDir = "up" | "down" | "flat";

/**
 * KPI — numeric metric tile. Three rows: kicker (label + optional icon),
 * value, sub (description or trend). Tonal variants tint a faint diagonal
 * wash so the surface scans as colored at a glance without competing
 * with the value typography.
 */
export function KPI({
  kicker,
  icon,
  value,
  sub,
  trend,
  trendValue,
  tone,
  onClick,
}: {
  kicker: ReactNode;
  icon?: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  trend?: TrendDir;
  trendValue?: ReactNode;
  tone?: Tone;
  onClick?: () => void;
}) {
  const cls = ["cf-kpi", tone ? `cf-kpi--${tone}` : ""].filter(Boolean).join(" ");
  return (
    <div
      className={cls}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      style={onClick ? { cursor: "pointer" } : undefined}
    >
      <div className="cf-kpi__kicker">
        {icon}
        {kicker}
      </div>
      <div className="cf-kpi__value">{value}</div>
      <div className="cf-kpi__sub">
        {sub}
        {trend && trendValue != null ? (
          <span className={`cf-kpi__trend cf-kpi__trend--${trend}`}>
            {trend === "up" ? "▲" : trend === "down" ? "▼" : "•"} {trendValue}
          </span>
        ) : null}
      </div>
    </div>
  );
}
