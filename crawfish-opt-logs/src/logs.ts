// Log-shape utilities. Three operations:
//
//   summarize — heuristic bucket: error / warning / info / stack-trace.
//               Returns the first + last N of each bucket. Lossless for the
//               errors; lossy for the noise. Beats blind `cat` 10–100×
//               on a typical npm/cargo/k8s dump.
//
//   grep      — pattern match with context lines + a cap. Faster +
//               token-thinner than asking an agent to grep itself.
//
//   tail_smart — last N lines, but reach back further to catch a stack-
//                trace block that starts before the N-line window.

const ERROR_RX = /\b(error|err!|fatal|panic|exception|traceback|failed|failure|denied)\b/i;
const WARN_RX = /\b(warn(ing)?|deprecat(ed|ion))\b/i;
const STACK_PREFIX_RX = /^\s+(at |File "|in [\w._-]+\.(rs|go|py|js|ts):)/;

export interface LogChunk {
  kind: "error" | "warning" | "info" | "stack";
  start_line: number;
  end_line: number;
  text: string;
}

export interface SummarizeResult {
  total_lines: number;
  errors: LogChunk[];
  warnings: LogChunk[];
  stacks: LogChunk[];
  /** Head + tail of the info stream. */
  info_head: string[];
  info_tail: string[];
  /** Always present so callers can route follow-up reads. */
  size_bytes: number;
}

interface SummarizeOptions {
  /** How many lines from the head + tail of the info stream to keep. */
  info_window?: number;
  /** Cap on errors returned. */
  max_errors?: number;
  /** Lines of context kept on each error block. */
  error_context?: number;
}

export function summarize(text: string, opts: SummarizeOptions = {}): SummarizeResult {
  const lines = text.split(/\r?\n/);
  const info_window = opts.info_window ?? 5;
  const max_errors = opts.max_errors ?? 20;
  const error_context = opts.error_context ?? 2;

  const errors: LogChunk[] = [];
  const warnings: LogChunk[] = [];
  const stacks: LogChunk[] = [];
  const info: string[] = [];

  // Walk lines once, grouping consecutive matches into chunks.
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (ERROR_RX.test(l)) {
      const start = Math.max(0, i - error_context);
      // Scan forward through continuation lines (stack frames) until we hit
      // a clearly non-error, non-stack line.
      let end = i;
      while (
        end + 1 < lines.length &&
        (ERROR_RX.test(lines[end + 1]) || STACK_PREFIX_RX.test(lines[end + 1]))
      ) {
        end++;
      }
      const block = lines.slice(start, end + 1 + error_context).join("\n");
      if (errors.length < max_errors) {
        errors.push({ kind: "error", start_line: start + 1, end_line: Math.min(lines.length, end + 1 + error_context), text: block });
      }
      i = end + error_context;
      continue;
    }
    if (WARN_RX.test(l)) {
      warnings.push({ kind: "warning", start_line: i + 1, end_line: i + 1, text: l });
      continue;
    }
    if (STACK_PREFIX_RX.test(l)) {
      // Standalone stack frame — usually picked up by the error scanner
      // above, but isolated occurrences land here.
      stacks.push({ kind: "stack", start_line: i + 1, end_line: i + 1, text: l });
      continue;
    }
    info.push(l);
  }

  return {
    total_lines: lines.length,
    errors,
    warnings,
    stacks: stacks.slice(0, 20),
    info_head: info.slice(0, info_window),
    info_tail: info.slice(Math.max(0, info.length - info_window)),
    size_bytes: text.length,
  };
}

export function grep(
  text: string,
  pattern: string | RegExp,
  opts: { n?: number; context?: number } = {},
): { matches: Array<{ line: number; text: string }>; total_matches: number } {
  const rx = typeof pattern === "string" ? new RegExp(pattern, "i") : pattern;
  const n = opts.n ?? 20;
  const context = opts.context ?? 0;
  const lines = text.split(/\r?\n/);
  const matches: Array<{ line: number; text: string }> = [];
  let total = 0;
  for (let i = 0; i < lines.length; i++) {
    if (!rx.test(lines[i])) continue;
    total++;
    if (matches.length >= n) continue;
    const start = Math.max(0, i - context);
    const end = Math.min(lines.length, i + context + 1);
    const block = lines.slice(start, end).join("\n");
    matches.push({ line: i + 1, text: block });
  }
  return { matches, total_matches: total };
}

export function tailSmart(text: string, n = 50): { lines: string[]; expanded_for_stack: boolean } {
  const lines = text.split(/\r?\n/);
  if (lines.length <= n) return { lines, expanded_for_stack: false };
  let start = lines.length - n;
  // If the tail window starts mid-stack, reach back to include the frame
  // header up to 50 more lines max.
  let expanded = false;
  for (let i = 0; i < 50 && start > 0; i++) {
    if (STACK_PREFIX_RX.test(lines[start])) {
      start--;
      expanded = true;
    } else if (start < lines.length - n && !STACK_PREFIX_RX.test(lines[start])) {
      // Stop once we walked past the frame block.
      break;
    } else {
      break;
    }
  }
  return { lines: lines.slice(start), expanded_for_stack: expanded };
}
