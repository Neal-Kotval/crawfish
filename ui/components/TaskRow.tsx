import type { ReactNode } from "react";

export type TaskStatus = "idle" | "live" | "good" | "warn";

export interface TaskRowProps {
  status?: TaskStatus;
  title: ReactNode;
  meta?: ReactNode;
  cost?: ReactNode;
  onClick?: () => void;
}

export function TaskRow({ status = "idle", title, meta, cost, onClick }: TaskRowProps) {
  const dotCls = {
    idle: "",
    live: "cfp-task__dot--live",
    good: "cfp-task__dot--good",
    warn: "cfp-task__dot--warn",
  }[status];

  return (
    <div className="cfp-task" onClick={onClick} role={onClick ? "button" : undefined}>
      <span className={`cfp-task__dot ${dotCls}`} />
      <div className="cfp-task__body">
        <div className="cfp-task__title">{title}</div>
        {meta ? <div className="cfp-task__meta">{meta}</div> : null}
      </div>
      {cost ? <span className="cfp-task__cost">{cost}</span> : null}
    </div>
  );
}
