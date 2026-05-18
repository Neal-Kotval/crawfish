/**
 * Download helpers for the marketing front door.
 *
 * Detects the visitor's platform, fetches the latest GitHub release once
 * (cached in localStorage for 5 minutes), and maps a platform key to the
 * correct release asset URL.
 */
import { useEffect, useState } from "react";

export type Platform = "mac-arm" | "mac-intel" | "linux" | "windows" | "unknown";

const REPO: string =
  (import.meta as { env?: Record<string, string> }).env?.VITE_GITHUB_REPO ||
  "Neal-Kotval/crawfish";
const CACHE_KEY = "cf:release";
const CACHE_TTL_MS = 5 * 60 * 1000;
export const RELEASES_FALLBACK_URL = `https://github.com/${REPO}/releases`;

interface UADataBrand { brand: string; version: string }
interface UAData {
  platform?: string;
  architecture?: string;
  getHighEntropyValues?: (hints: string[]) => Promise<{ architecture?: string; platform?: string }>;
  brands?: UADataBrand[];
}

export function detectPlatform(): Platform {
  if (typeof navigator === "undefined") return "unknown";
  const nav = navigator as Navigator & { userAgentData?: UAData };
  const uaData = nav.userAgentData;
  if (uaData?.platform) {
    const plat = uaData.platform.toLowerCase();
    const arch = (uaData.architecture || "").toLowerCase();
    if (plat.includes("mac")) return arch.includes("arm") ? "mac-arm" : "mac-intel";
    if (plat.includes("win")) return "windows";
    if (plat.includes("linux")) return "linux";
  }
  const ua = (nav.userAgent || "").toLowerCase();
  if (ua.includes("mac os") || ua.includes("macintosh")) {
    // Heuristic: Apple Silicon Macs running Safari/Firefox spoof Intel UA.
    // Default to mac-arm for modern Macs since 2020+ are arm.
    return "mac-arm";
  }
  if (ua.includes("windows")) return "windows";
  if (ua.includes("linux")) return "linux";
  return "unknown";
}

export interface ReleaseAsset {
  name: string;
  browser_download_url: string;
}
export interface Release {
  tag_name?: string;
  html_url: string;
  assets: ReleaseAsset[];
}

interface CachedRelease { release: Release; ts: number }

function readCache(): Release | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as CachedRelease;
    if (Date.now() - parsed.ts > CACHE_TTL_MS) return null;
    return parsed.release;
  } catch {
    return null;
  }
}

function writeCache(release: Release): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify({ release, ts: Date.now() }));
  } catch {
    /* ignore quota errors */
  }
}

export function useLatestRelease(): { release: Release | null; loading: boolean; error: Error | null } {
  const [release, setRelease] = useState<Release | null>(() => readCache());
  const [loading, setLoading] = useState<boolean>(release === null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (release) return;
    let cancelled = false;
    setLoading(true);
    fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
      .then((r) => {
        if (!r.ok) throw new Error(`GitHub API ${r.status}`);
        return r.json() as Promise<Release>;
      })
      .then((json) => {
        if (cancelled) return;
        writeCache(json);
        setRelease(json);
        setError(null);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [release]);

  return { release, loading, error };
}

const PATTERNS: Record<Exclude<Platform, "unknown">, RegExp[]> = {
  "mac-arm":   [/aarch64.*\.dmg$/i, /arm64.*\.dmg$/i, /apple[-_]silicon.*\.dmg$/i],
  "mac-intel": [/x64.*\.dmg$/i, /x86[_-]64.*\.dmg$/i, /intel.*\.dmg$/i, /\.dmg$/i],
  "linux":     [/\.AppImage$/i, /x86[_-]64.*\.AppImage$/i],
  "windows":   [/\.msi$/i, /x64.*\.msi$/i],
};

export function assetUrlFor(release: Release | null, platform: Platform): string {
  if (!release) return RELEASES_FALLBACK_URL;
  if (platform === "unknown") return release.html_url || RELEASES_FALLBACK_URL;
  const patterns = PATTERNS[platform];
  for (const pat of patterns) {
    const hit = release.assets.find((a) => pat.test(a.name));
    if (hit) return hit.browser_download_url;
  }
  return release.html_url || RELEASES_FALLBACK_URL;
}

export const PLATFORM_LABELS: Record<Platform, string> = {
  "mac-arm":   "Mac (Apple Silicon)",
  "mac-intel": "Mac (Intel)",
  "linux":     "Linux",
  "windows":   "Windows",
  "unknown":   "your platform",
};
