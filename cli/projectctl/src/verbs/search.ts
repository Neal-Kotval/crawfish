import { searchTasks, type SearchResult } from "../search.js";

export function search(repoRoot: string, query: string): SearchResult {
  return searchTasks(repoRoot, query);
}
