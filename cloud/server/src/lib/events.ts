/**
 * In-process board event hub (SSE fan-out).
 *
 * Phase 4 / audit B3: the cloud tier needs realtime so the board updates live.
 * This is a single-process EventEmitter hub keyed by projectId — sufficient for
 * a single server instance. A multi-instance deployment would back this with
 * Redis pub/sub or Postgres LISTEN/NOTIFY (tracked follow-up); the publish/
 * subscribe surface below stays the same.
 */
import { EventEmitter } from "node:events";

const hub = new EventEmitter();
hub.setMaxListeners(0); // many concurrent SSE subscribers per project

export interface BoardEvent {
  kind: string; // mirrors Activity kind (task_created | status_changed | …)
  taskId?: string | null;
  payload?: unknown;
  at: string; // ISO timestamp
}

function channel(projectId: string): string {
  return `board:${projectId}`;
}

export function publishBoard(projectId: string, ev: BoardEvent): void {
  hub.emit(channel(projectId), ev);
}

/** Subscribe to a project's board events. Returns an unsubscribe function. */
export function subscribeBoard(projectId: string, fn: (ev: BoardEvent) => void): () => void {
  const ch = channel(projectId);
  hub.on(ch, fn);
  return () => hub.off(ch, fn);
}
