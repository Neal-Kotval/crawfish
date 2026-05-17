import type { ReactNode } from "react";
import { Pill } from "./Pill";

export type NodeVariant = "neutral" | "accent" | "you";

export interface NodeProps {
  x: number;
  y: number;
  w?: number;
  h?: number;
  name: string;
  role?: ReactNode;
  runtime?: ReactNode;
  status?: "live" | "idle" | "ready";
  variant?: NodeVariant;
  selected?: boolean;
  idle?: boolean;
  onClick?: () => void;
}

export function Node({
  x, y, w = 188, h = 86,
  name, role, runtime, status,
  variant = "neutral", selected, idle, onClick,
}: NodeProps) {
  const cls = [
    "cfp-node",
    variant === "accent" ? "cfp-node--accent" : "",
    variant === "you" ? "cfp-node--you" : "",
    idle ? "cfp-node--idle" : "",
    selected ? "cfp-node--selected" : "",
  ].filter(Boolean).join(" ");

  const statusTone = status === "live" ? "ink" : status === "ready" ? "good" : "neutral";

  return (
    <div
      className={cls}
      style={{ left: x, top: y, width: w, height: h }}
      onClick={onClick}
      role={onClick ? "button" : undefined}
    >
      <div className="cfp-node__head">
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div className="cfp-node__avatar">{name.slice(0, 1)}</div>
          <div className="cfp-node__name">{name}</div>
        </div>
        {status ? (
          <Pill tone={statusTone} live={status === "live"}>{status}</Pill>
        ) : null}
      </div>
      <div className="cfp-node__foot">
        {role ? <div className="cfp-node__role">{role}</div> : null}
        {runtime ? <div className="cfp-node__rt">{runtime}</div> : null}
      </div>
    </div>
  );
}
