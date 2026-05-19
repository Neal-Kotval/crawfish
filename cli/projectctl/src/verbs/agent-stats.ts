import { getAgentStats } from "../agent-stats.js";

export function agentStats(repoRoot: string, agentId: string): ReturnType<typeof getAgentStats> {
  return getAgentStats(repoRoot, agentId);
}
