import type { ReactNode } from "react";

export interface TabSpec {
  id: string;
  label: ReactNode;
  count?: number | string;
}

export interface TabsProps {
  tabs: TabSpec[];
  active: string;
  onChange?: (id: string) => void;
  className?: string;
}

export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div className={`cfp-tabs ${className ?? ""}`.trim()} role="tablist">
      {tabs.map((t) => {
        const isActive = t.id === active;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`cfp-tab ${isActive ? "cfp-tab--active" : ""}`.trim()}
            onClick={() => onChange?.(t.id)}
          >
            <span>{t.label}</span>
            {t.count !== undefined ? <span className="cfp-tab__count">{t.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
