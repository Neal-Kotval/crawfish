import { ReactNode } from "react";

/**
 * EmptyState — the canonical "no data yet" block. Wraps .cf-empty and
 * .cf-empty__title so dash and lens render identical empty states.
 *
 * Slots (all optional except `title`):
 *   - illustration: a small inline SVG (typically from
 *     `crawfish-dash/web/src/components/Spot.tsx`) shown above the title to
 *     warm up an otherwise empty surface. See DESIGN.md §5.
 *   - body: descriptive copy. Falls back to `children` when omitted, so
 *     existing call sites that pass copy as children continue to work.
 *   - cta: a single primary action node (typically a `<button className=
 *     "cf-btn cf-btn--primary">`). Rendered below the body.
 */
export function EmptyState({
  title,
  body,
  illustration,
  cta,
  children,
}: {
  title: string;
  body?: ReactNode;
  illustration?: ReactNode;
  cta?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="cf-empty">
      {illustration ? (
        <div className="cf-empty__illustration">{illustration}</div>
      ) : null}
      <div className="cf-empty__title">{title}</div>
      {body ? <div className="cf-empty__body">{body}</div> : null}
      {children ? <div>{children}</div> : null}
      {cta ? <div className="cf-empty__cta">{cta}</div> : null}
    </div>
  );
}
