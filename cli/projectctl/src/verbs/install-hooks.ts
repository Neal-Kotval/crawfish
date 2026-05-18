import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";

interface HookEntry {
  matcher?: string;
  command: string;
  _crawfish?: boolean;
}

interface Settings {
  hooks?: Record<string, HookEntry[]>;
  [k: string]: unknown;
}

const HOOKS: Record<string, HookEntry[]> = {
  SessionEnd: [
    { command: "crawfish-projectctl activity record", _crawfish: true },
  ],
  PostToolUse: [
    { matcher: "Edit|Write", command: "crawfish-projectctl refresh --debounce 30000", _crawfish: true },
  ],
  UserPromptSubmit: [
    { command: "crawfish-projectctl refresh memory.md", _crawfish: true },
  ],
};

function settingsPath(repoRoot: string): string {
  return join(repoRoot, ".claude", "settings.json");
}

function loadSettings(repoRoot: string): Settings {
  const p = settingsPath(repoRoot);
  if (!existsSync(p)) return {};
  return JSON.parse(readFileSync(p, "utf8")) as Settings;
}

function saveSettings(repoRoot: string, settings: Settings): void {
  const p = settingsPath(repoRoot);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(settings, null, 2) + "\n");
}

export function installHooks(repoRoot: string): void {
  const settings = loadSettings(repoRoot);
  settings.hooks = settings.hooks ?? {};
  for (const [event, entries] of Object.entries(HOOKS)) {
    const current = settings.hooks[event] ?? [];
    const withoutOurs = current.filter((h) => !h._crawfish);
    settings.hooks[event] = [...withoutOurs, ...entries];
  }
  saveSettings(repoRoot, settings);
}

export function uninstallHooks(repoRoot: string): void {
  const settings = loadSettings(repoRoot);
  if (!settings.hooks) return;
  for (const event of Object.keys(settings.hooks)) {
    settings.hooks[event] = settings.hooks[event].filter((h) => !h._crawfish);
    if (settings.hooks[event].length === 0) delete settings.hooks[event];
  }
  if (Object.keys(settings.hooks).length === 0) delete settings.hooks;
  saveSettings(repoRoot, settings);
}
