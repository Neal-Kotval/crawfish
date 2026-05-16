import { ReactNode } from "react";

/**
 * Diagonal decorative glyph anchored to the bottom-right corner of a card.
 * Rotated 45° so it bleeds outward; the parent must `position: relative` and
 * (typically) `overflow: hidden` so the rotation crops to a triangle.
 *
 * The icon prop is any SVG element. Stroke colors should use `currentColor`
 * — we set color: var(--cf-fg) here and let opacity do the fading.
 */
export function CardCorner({
  icon,
  size = 150,
  opacity = 0.1,
  offset = -28,
}: {
  icon: ReactNode;
  /** px square box for the SVG container. Larger = more bleed. */
  size?: number;
  opacity?: number;
  /** how far past the corner to push (negative = bleeds outside box). */
  offset?: number;
}) {
  return (
    <div
      aria-hidden="true"
      style={{
        position: "absolute",
        bottom: offset,
        right: offset,
        width: size,
        height: size,
        transform: "rotate(-45deg)",
        transformOrigin: "center",
        opacity,
        pointerEvents: "none",
        color: "var(--cf-fg)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {icon}
    </div>
  );
}

// ─── stock SVG icons (lucide-flavored, currentColor strokes) ───────────────
//
// Each icon renders inside CardCorner — rotated 45° by the parent. They use
// stroke="currentColor" so a single `color` cascade colors the whole set.

const ICON_PROPS = {
  width: "100%",
  height: "100%",
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export const CornerIcons = {
  bot: (
    <svg {...ICON_PROPS}>
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <path d="M12 4v4" />
      <circle cx="12" cy="3" r="1" />
      <circle cx="9" cy="13" r="1" />
      <circle cx="15" cy="13" r="1" />
      <path d="M8 17h8" />
    </svg>
  ),
  shield: (
    <svg {...ICON_PROPS}>
      <path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6l-8-3z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  ),
  zap: (
    <svg {...ICON_PROPS}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8z" />
    </svg>
  ),
  trending: (
    <svg {...ICON_PROPS}>
      <path d="M3 17l6-6 4 4 8-8" />
      <path d="M14 7h7v7" />
    </svg>
  ),
  bars: (
    <svg {...ICON_PROPS}>
      <rect x="4" y="12" width="3" height="8" rx="0.5" />
      <rect x="10" y="7" width="3" height="13" rx="0.5" />
      <rect x="16" y="3" width="3" height="17" rx="0.5" />
    </svg>
  ),
  coins: (
    <svg {...ICON_PROPS}>
      <circle cx="9" cy="9" r="5" />
      <path d="M14.5 6.5a5 5 0 1 1 0 9" />
      <path d="M9 7v4M7 9h4" />
    </svg>
  ),
  spark: (
    <svg {...ICON_PROPS}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4" />
      <path d="M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />
    </svg>
  ),
  book: (
    <svg {...ICON_PROPS}>
      <path d="M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2V5z" />
      <path d="M8 7h8M8 11h8M8 15h5" />
    </svg>
  ),
  list: (
    <svg {...ICON_PROPS}>
      <path d="M8 6h13M8 12h13M8 18h13" />
      <circle cx="4" cy="6" r="1" />
      <circle cx="4" cy="12" r="1" />
      <circle cx="4" cy="18" r="1" />
    </svg>
  ),
  beaker: (
    <svg {...ICON_PROPS}>
      <path d="M9 3h6M10 3v6L4 19a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-6-10V3" />
      <path d="M7 14h10" />
    </svg>
  ),
  doc: (
    <svg {...ICON_PROPS}>
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
      <path d="M14 3v6h6" />
      <path d="M8 13h8M8 17h5" />
    </svg>
  ),
  search: (
    <svg {...ICON_PROPS}>
      <circle cx="11" cy="11" r="6" />
      <path d="m20 20-4.5-4.5" />
    </svg>
  ),
  map: (
    <svg {...ICON_PROPS}>
      <path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2z" />
      <path d="M9 4v14M15 6v14" />
    </svg>
  ),
  lobster: (
    <svg {...ICON_PROPS}>
      <path d="M5 10c0-3 3-6 7-6s7 3 7 6c0 2-1 3-1 3s2 0 2 3-3 4-3 4H7s-3-1-3-4 2-3 2-3-1-1-1-3z" />
      <path d="M9 8l-3-3M15 8l3-3" />
      <path d="M9 16h6" />
    </svg>
  ),
};

export type CornerIconName = keyof typeof CornerIcons;
