import { CSSProperties, ReactNode } from "react";
import { CardCorner, CornerIcons, type CornerIconName } from "./CardCorner";

// Temporary kill-switch for the diagonal corner glyphs. The icon code
// stays wired up — flip this back to true to re-enable everywhere.
const CORNER_ICONS_ENABLED = false;

/**
 * Base card primitive — wraps the .cf-card class and adds slots for the
 * diagonal corner decoration. Used by every overview card / template card
 * in the dash and (planned) lens. Position: relative + overflow: hidden so
 * the rotated corner glyph crops cleanly inside the rounded border.
 */
export function Card({
  children,
  onClick,
  active,
  cornerIcon,
  cornerOpacity,
  className,
  style,
  role,
  ariaLabel,
}: {
  children: ReactNode;
  onClick?: () => void;
  /** Highlights the card with the accent border. */
  active?: boolean;
  /** Either a named stock icon or a custom SVG element. */
  cornerIcon?: CornerIconName | ReactNode;
  cornerOpacity?: number;
  className?: string;
  style?: CSSProperties;
  role?: string;
  ariaLabel?: string;
}) {
  const icon =
    typeof cornerIcon === "string"
      ? CornerIcons[cornerIcon as CornerIconName]
      : cornerIcon;

  return (
    <div
      className={"cf-card" + (className ? ` ${className}` : "")}
      onClick={onClick}
      role={role ?? (onClick ? "button" : undefined)}
      aria-label={ariaLabel}
      style={{
        position: "relative",
        overflow: "hidden",
        ...(active
          ? { borderColor: "var(--cf-accent, var(--cf-fg))" }
          : null),
        ...style,
      }}
    >
      {children}
      {CORNER_ICONS_ENABLED && icon ? (
        <CardCorner icon={icon} opacity={cornerOpacity} />
      ) : null}
    </div>
  );
}
