import { ReactNode } from "react";

type Size = "sm" | "md" | "lg" | "xl";
type Tone = 1 | 2 | 3 | 4 | 5 | 6;

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function toneFor(seed: string): Tone {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  return (((h % 6) + 1) as Tone);
}

/**
 * Avatar — circular initials chip with stable hashed color. Pair with
 * <AvatarStack> for collaborator clusters.
 */
export function Avatar({
  name,
  size = "md",
  tone,
  title,
}: {
  name: string;
  size?: Size;
  tone?: Tone;
  title?: string;
}) {
  const cls = [
    "cf-avatar",
    size !== "md" ? `cf-avatar--${size}` : "",
    `cf-avatar--${tone ?? toneFor(name)}`,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={cls} title={title ?? name} aria-label={name}>
      {initialsOf(name)}
    </span>
  );
}

export function AvatarStack({ children }: { children: ReactNode }) {
  return <span className="cf-avatar-stack">{children}</span>;
}
