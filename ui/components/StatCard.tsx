import { ReactNode } from "react";
import { Card } from "./Card";
import type { CornerIconName } from "./CardCorner";

/**
 * StatCard — overview tile used on the dash Dashboard tab. Three lines:
 * a kicker (icon + label), a big value, and a small subtitle. Optional
 * diagonal corner glyph reinforces the category at a glance.
 */
export function StatCard({
  icon,
  label,
  value,
  sub,
  onClick,
  cornerIcon,
}: {
  icon: ReactNode;
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  onClick?: () => void;
  cornerIcon?: CornerIconName | ReactNode;
}) {
  return (
    <Card onClick={onClick} cornerIcon={cornerIcon} ariaLabel={label}>
      <div className="cf-card__header">
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ fontSize: 20 }}>{icon}</span>
          <div
            style={{
              fontSize: 12,
              color: "var(--cf-fg-secondary)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              fontWeight: 600,
            }}
          >
            {label}
          </div>
        </div>
      </div>
      <div
        style={{
          fontSize: 28,
          fontWeight: 600,
          letterSpacing: "-0.02em",
          color: "var(--cf-fg)",
          lineHeight: 1.1,
        }}
      >
        {value}
      </div>
      {sub ? (
        <div style={{ fontSize: 12, color: "var(--cf-fg-secondary)" }}>
          {sub}
        </div>
      ) : null}
    </Card>
  );
}
