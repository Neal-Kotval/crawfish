import { ReactNode } from "react";

export interface SuggestionProps {
  /** Short headline — sentence case, ends without a period. */
  title: string;
  /** One-sentence "why now" body. Plain English. */
  body: string;
  /** Optional call-to-action label rendered as a styled inline link. */
  cta?: string;
  /** Optional icon — an emoji or a small inline SVG. */
  icon?: ReactNode;
  /** Click handler — fires on row click and CTA click. */
  onClick?: () => void;
  /** Optional dismiss callback. Renders an × in the top-right when set. */
  onDismiss?: () => void;
}

/**
 * Suggestion card — used on the Home dashboard to surface the next likely
 * action ("create a cycle", "try an optimizer", etc.). One card per row,
 * stacked. Click anywhere in the card to act; the × hides it.
 */
export function Suggestion({
  title,
  body,
  cta,
  icon,
  onClick,
  onDismiss,
}: SuggestionProps) {
  return (
    <button
      type="button"
      className="cf-suggestion"
      onClick={onClick}
      aria-label={title}
    >
      {icon !== undefined && (
        <span className="cf-suggestion__icon" aria-hidden>
          {icon}
        </span>
      )}
      <span className="cf-suggestion__body">
        <span className="cf-suggestion__title">{title}</span>
        <span className="cf-suggestion__text">{body}</span>
        {cta && (
          <span className="cf-suggestion__cta">
            {cta} <span aria-hidden>→</span>
          </span>
        )}
      </span>
      {onDismiss && (
        <span
          role="button"
          tabIndex={0}
          className="cf-suggestion__dismiss"
          aria-label="Dismiss"
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              e.stopPropagation();
              onDismiss();
            }
          }}
        >
          ×
        </span>
      )}
    </button>
  );
}
