import { runRouterPass, type RouterPassResult } from "../router.js";

export function routerRun(repoRoot: string, opts: { dryRun?: boolean } = {}): RouterPassResult {
  return runRouterPass(repoRoot, { dryRun: opts.dryRun });
}
