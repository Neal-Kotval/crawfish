import type { ReactNode } from "react";

export interface EyebrowProps {
  children: ReactNode;
  as?: "div" | "span" | "p";
  className?: string;
  style?: React.CSSProperties;
}

export function Eyebrow({ children, as: Tag = "div", className, style }: EyebrowProps) {
  return (
    <Tag className={`cf-eyebrow ${className ?? ""}`.trim()} style={style}>
      {children}
    </Tag>
  );
}
