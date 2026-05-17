import { ReactNode } from "react";

export interface SegmentedItem<V extends string> {
  value: V;
  label: ReactNode;
}

/**
 * iOS-style segmented control. Single-select; keyboard accessible via
 * native buttons. Use for view toggles (Day / Week / Month), small
 * orthogonal filter sets, or any switch between 2–4 mutually exclusive
 * states. For more than 4 options prefer a Tabs primitive.
 */
export function Segmented<V extends string>({
  value,
  onChange,
  items,
  ariaLabel,
}: {
  value: V;
  onChange: (v: V) => void;
  items: SegmentedItem<V>[];
  ariaLabel?: string;
}) {
  return (
    <div className="cf-segmented" role="tablist" aria-label={ariaLabel}>
      {items.map((it) => {
        const active = it.value === value;
        return (
          <button
            key={it.value}
            type="button"
            role="tab"
            aria-pressed={active}
            className={"cf-segmented__item" + (active ? " cf-segmented__item--active" : "")}
            onClick={() => onChange(it.value)}
          >
            {it.label}
          </button>
        );
      })}
    </div>
  );
}
