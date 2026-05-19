// Barrel for templates module. Re-exports the overlay merger so callers
// (the orgctl CLI, the describe-my-org wizard) can import from a stable
// path: `crawfish-orgctl/templates`.
export { applyOverlay, applyOverlays } from "./apply.js";
export type {
  BaseTemplate,
  OrgConfig,
  Overlay,
  TemplateMember,
  TemplateCron,
} from "./apply.js";
