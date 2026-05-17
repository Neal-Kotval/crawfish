import type { ReactNode } from "react";
import { Icons } from "./Icon";

export interface TitleBarProps {
  org: string;
  orgGlyph?: string;
  searchPlaceholder?: string;
  costToday?: ReactNode;
  tokensPerHr?: ReactNode;
  userInitial?: string;
  onOrgSwitch?: () => void;
  onSearch?: () => void;
  onBell?: () => void;
  onAvatar?: () => void;
}

export function TitleBar({
  org,
  orgGlyph = "cf",
  searchPlaceholder = "Find a task, agent, or chunk…",
  costToday,
  tokensPerHr,
  userInitial = "F",
  onOrgSwitch,
  onSearch,
  onBell,
  onAvatar,
}: TitleBarProps) {
  /* Inside Tauri the OS draws real traffic lights (titleBarStyle:Overlay).
   * Outside (browser preview, web platform), we draw decorative dots so the
   * chrome still reads as a "window" in the hi-fi artboard sense. */
  const inTauri = typeof window !== "undefined" &&
    (typeof (window as any).__TAURI_INTERNALS__ !== "undefined" ||
     typeof (window as any).__TAURI__ !== "undefined");

  return (
    <div className="cfp-titlebar" style={inTauri ? { paddingLeft: 78 } : undefined}>
      {inTauri ? null : (
        <div className="cfp-titlebar__lights">
          <span className="cfp-titlebar__light cfp-titlebar__light--r" />
          <span className="cfp-titlebar__light cfp-titlebar__light--y" />
          <span className="cfp-titlebar__light cfp-titlebar__light--g" />
        </div>
      )}

      <button type="button" className="cfp-titlebar__org" onClick={onOrgSwitch}>
        <div className="cfp-titlebar__brand">{orgGlyph}</div>
        <span style={{ fontWeight: 600, letterSpacing: "-0.008em" }}>{org}</span>
        <span style={{ color: "var(--ink-mute)" }}>{Icons.chevD}</span>
      </button>

      <div className="cfp-titlebar__center">
        <button type="button" className="cfp-titlebar__search" onClick={onSearch}>
          <span style={{ color: "var(--ink-mute)" }}>{Icons.search}</span>
          <span>{searchPlaceholder}</span>
          <span className="cfp-titlebar__kbd">⌘K</span>
        </button>
      </div>

      <div className="cfp-titlebar__right">
        {(costToday || tokensPerHr) && (
          <div className="cfp-titlebar__meter">
            {costToday ? (
              <>
                <span style={{ color: "var(--accent)" }}>●</span>
                <span className="cf-num">{costToday}</span>
                <span style={{ color: "var(--ink-faint)" }}>today</span>
              </>
            ) : null}
            {costToday && tokensPerHr ? (
              <span style={{ width: 1, height: 12, background: "var(--rule-3)", margin: "0 2px" }} />
            ) : null}
            {tokensPerHr ? (
              <>
                <span className="cf-num">{tokensPerHr}</span>
                <span style={{ color: "var(--ink-faint)" }}>tok / hr</span>
              </>
            ) : null}
          </div>
        )}
        <button type="button" className="cfp-titlebar__bell" onClick={onBell}>{Icons.bell}</button>
        <button type="button" className="cfp-titlebar__avatar" onClick={onAvatar}>{userInitial}</button>
      </div>
    </div>
  );
}
