import type { ReactNode } from "react";

export interface IconProps {
  size?: number;
  stroke?: number;
  className?: string;
  children: ReactNode;
}

export function Icon({ size = 16, stroke = 1.6, className, children }: IconProps) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  );
}

/* ── The Crawfish icon set ──────────────────────────────────────────── */
export const Icons = {
  canvas:    (<Icon><circle cx="6" cy="6" r="2.2"/><circle cx="18" cy="6" r="2.2"/><circle cx="12" cy="18" r="2.2"/><path d="M7.5 7.5l3.5 8M16.5 7.5l-3.5 8"/></Icon>),
  board:     (<Icon><rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9 4.5v15M15 4.5v15"/></Icon>),
  sessions:  (<Icon><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></Icon>),
  knowledge: (<Icon><path d="M4 5.5a2 2 0 0 1 2-2h12v15H6.5a2.5 2.5 0 0 0-2.5 2.5z"/><path d="M4 18.5a2.5 2.5 0 0 1 2.5-2.5H18"/></Icon>),
  diagnoses: (<Icon><path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17v.5"/></Icon>),
  skills:    (<Icon><path d="M4 8h6V4M20 16h-6v4M14 4h6v6M10 20H4v-6"/></Icon>),
  settings:  (<Icon><circle cx="12" cy="12" r="3"/><path d="M12 3v2.5M12 18.5V21M3 12h2.5M18.5 12H21M5.6 5.6l1.8 1.8M16.6 16.6l1.8 1.8M5.6 18.4l1.8-1.8M16.6 7.4l1.8-1.8"/></Icon>),
  bell:      (<Icon><path d="M6 9a6 6 0 1 1 12 0v5l1.5 2.5h-15L6 14z"/><path d="M10 19a2 2 0 0 0 4 0"/></Icon>),
  plus:      (<Icon><path d="M12 5v14M5 12h14"/></Icon>),
  search:    (<Icon><circle cx="11" cy="11" r="6"/><path d="M16 16l4 4"/></Icon>),
  chev:      (<Icon><path d="M9 6l6 6-6 6"/></Icon>),
  chevD:     (<Icon><path d="M6 9l6 6 6-6"/></Icon>),
  bolt:      (<Icon><path d="M13 3L5 14h6l-1 7 8-11h-6z"/></Icon>),
  play:      (<Icon><path d="M7 5l12 7-12 7z"/></Icon>),
  pause:     (<Icon><path d="M7 5v14M17 5v14"/></Icon>),
  code:      (<Icon><path d="M8 8l-4 4 4 4M16 8l4 4-4 4M14 4l-4 16"/></Icon>),
  history:   (<Icon><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 7v5l3 2"/></Icon>),
  pr:        (<Icon><circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/><path d="M6 8v8M18 16V8a4 4 0 0 0-4-4h-2l3-3M12 4l3 3"/></Icon>),
};
