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
        <div className="cf-row cf-gap-3">
          <span className="cf-text-lg">{icon}</span>
          <div className="cf-kicker">{label}</div>
        </div>
      </div>
      <div className="cf-text-2xl cf-num">{value}</div>
      {sub ? <div className="cf-text-sm cf-fg-secondary">{sub}</div> : null}
    </Card>
  );
}
