# ADR 0016 — Host-side node isolation is a `Jail` abstraction (Linux: bwrap+seccomp+Landlock · macOS: `sandbox-exec`)

**Status:** Accepted · **Date:** 2026-06-21 · **Milestone:** Phase 2 (Sandboxed pipelines)

> Spike CRA-188 (P2-SPIKE). Splits the **OS-mechanism + portability** question out of
> CRA-183 (the ruvLLM/rvagent perf evaluation). The verdict here gates the mechanism
> choice in **CRA-179** (Sandboxed pipelines — out-of-process, folder-scoped host-side
> execution). Numbering: 0011 reserved (ruvLLM), 0013/0014/0015 taken → this is **0016**.

## Context

CRA-179 runs **host-side node code** — sources/sinks/filters that execute *our* and
*users'* Python (not the `claude -p` child) — out-of-process, scoped to an allowed folder,
with **network denied by default**. This is the host-side leg of the security spine
(`SECURITY.md`): code reachable from `Flow.FLUID` (untrusted session data) must run jailed
so a prompt-injection-driven node cannot read outside its folder or exfiltrate over the
network. CRA-186's broker depends on the property that *folder escape and undeclared egress
are actually blocked and audited* (CRA-189 emissions).

The enforcement primitive is **OS-sensitive**:

- **Linux** — unprivileged `seccomp-bpf` syscall filtering + user/mount/**net** namespaces
  (loopback-only), with **Landlock** LSM for path allow-listing. Packaged cleanly by
  **bubblewrap** (`bwrap`, the Flatpak sandbox) or **nsjail**.
- **macOS** — `sandbox-exec` (Seatbelt profiles): `(deny default)` + `(allow file-read*
  file-write* (subpath …))` + `(deny network*)`. **Deprecated-but-present** and load-bearing
  in Apple's own App Sandbox; the warning goes to stderr, the mechanism still enforces on
  macOS 15.
- **Windows** — no clean unprivileged primitive; **deferred per ADR 0009** (same OS matrix:
  macOS + Linux now).

DSPy-style heavy infra (the rvagent **WASM** sandbox) is the *separate* CRA-183 question
(is ruvLLM fast enough). This ADR evaluates WASM **only** as a portability option for the
OS-mechanism question, and rejects it here on Python-fidelity grounds (below).

This mirrors a now-standard industry shape: OpenAI Codex's `SandboxPolicy → SandboxManager
→ platform backend` (Landlock+seccomp / Seatbelt / restricted-token), Claude Code's own
sandbox, and projects like `ai-jail` and `agent-seatbelt-sandbox`.

## Options

| Mechanism | Portability (mac/Linux now) | FS-scope + net-deny strength | Footprint / deps | Testability (injectable, escape-asserts) | Taint across boundary |
|---|---|---|---|---|---|
| **`bwrap`/nsjail + seccomp + Landlock** (Linux) | Linux only | **Strong** — net namespace = loopback-only (no egress path exists); mount ns + Landlock allow-list = hard folder scope; seccomp drops dangerous syscalls. Unprivileged (user-ns), no setuid. | `bwrap` is a small static binary (Flatpak ubiquity); kernel ≥5.13 for Landlock, ≥6.7 for net allow-list. No Python dep. | **Good** — `Jail` interface fakeable in-proc; a few real `bwrap` integration tests, skipped when binary/kernel absent. | Serialize taint into child argv/env/stdin; child re-tags outputs (out-of-proc, so taint is explicit, not shared memory). |
| **`sandbox-exec` / Seatbelt** (macOS) | macOS only | **Strong** — `(deny default)`, subpath read/write allow, `(deny network*)`. Child processes inherit the profile. Caveat: deprecated (removal risk, low). | Zero deps — ships with macOS. Warning to stderr. | **Good** — same `Jail` fake; real Seatbelt integration test gated to `sys.platform=="darwin"`. | Same as Linux — explicit cross-process serialization. |
| **WASM (wasmtime / pyodide-style)** | **Portable (all OS)** | **Strong by default** (no ambient authority; WASI `--dir` preopen = capability-scoped FS; no socket imports = no egress) **but** | Heavy: a Wasm runtime + a WASI CPython. **Pyodide is browser/Node-only server-side; WASI CPython lacks sockets/SSL and breaks C-extension nodes (numpy/pandas/native SDKs).** | Deterministic and very testable — but the fidelity gap makes the *thing under test* not real host Python. | Same serialization story. |
| **Pure subprocess + drop-privs + rlimits** | Portable | **Weak** — no FS allow-list (only `os.chroot`/cwd, racy, needs root) and **no real egress block** without namespaces/Seatbelt. `rlimit` caps resources, not reach. | Zero deps. | Testable, but there's little to assert — it doesn't block the escapes. | n/a |

## Decision

**Adopt a single `Jail` abstraction with two real backends — Linux (`bwrap` + seccomp +
Landlock) and macOS (`sandbox-exec`/Seatbelt) — plus an injectable in-process fake for
tests. WASM is deferred (tracked under CRA-183 if rvagent ever pays its way as an *optional*
high-isolation backend). Windows is deferred (ADR 0009). A `nojail` passthrough exists only
for explicit opt-out, never the default for FLUID-reachable code.**

Rationale: the two native primitives give the **strong** folder-scope + hard net-deny
guarantee that CRA-186's broker requires, at **near-zero footprint** and **full Python
fidelity** (C-extension nodes just work). WASM matches the guarantee but fails fidelity —
no sockets, no native extensions, no server-side pyodide — so it cannot run arbitrary
host-side node code today. The pure-subprocess fallback is rejected: it does not actually
block egress. Selecting the backend is a runtime/OS detail behind one interface, exactly the
"swappable seam" rule from ADR 0001 — backend choice never changes node code or the security
properties.

### The `Jail` interface contract (handed to CRA-179)

A behavioural ABC (ADR 0004), one owner, imported by the node runner — never a concrete
backend imported directly. Backends are selected by a factory; tests inject `FakeJail`.

```python
class Jail(ABC):
    """Out-of-process, folder-scoped, network-denied execution of host-side node code."""

    @abstractmethod
    def run(
        self,
        cmd: Sequence[str],
        *,
        allow_paths: Sequence[JailPath],   # (host_path, mode: 'ro'|'rw'); STATIC-only, never FLUID
        allow_net: bool = False,           # default deny; True is an explicit, audited grant
        env: Mapping[str, str],            # resolved-by-reference secrets only; never logged/in-prompt
        stdin: bytes | None = None,
        cwd: JailPath | None = None,
        timeout_s: float | None = None,
        taint: TaintSet = frozenset(),     # serialized in; child re-emits on outputs
    ) -> JailResult: ...

    @property
    @abstractmethod
    def kind(self) -> str: ...             # 'bwrap' | 'seatbelt' | 'fake' | 'nojail'


@dataclass(frozen=True)                    # Freezable per ADR 0006 — a frozen run spec
class JailResult:
    exit_code: int
    stdout: bytes
    stderr: bytes
    out_taint: TaintSet                    # taint propagated back out of the child
    denied: tuple[Denial, ...]             # audited escape attempts (folder/net), → CRA-189 emissions
    timed_out: bool


def select_jail(policy: SandboxPolicy) -> Jail: ...   # OS-sniffing factory; raises on Windows
```

**Invariants CRA-179 must uphold (security spine):** `allow_paths` and `allow_net` derive
from **static** node config only — never from `Flow.FLUID` input (ADR: consequential targets
are static-only). Secrets enter via `env` resolved-by-reference and are never logged or
placed in-prompt. The child process is the **taint boundary**: anything reachable from FLUID
runs jailed, and `out_taint` re-tags every value crossing back. Every `Denial` is emitted to
the audit ledger (CRA-189), satisfying the broker's (CRA-186) "blocked **and audited**"
contract. **Type-registry rehydration**: the child reconstructs `default_registry` at startup
(structural types travel as serialized descriptors, not Python identities) so
`parameters_compatible` holds across the boundary — an acceptance criterion of CRA-188.

## Testing strategy

The jail is **injectable**, so unit tests assert policy without spawning a real sandbox:

1. **`FakeJail` (in-process transport)** — default in unit tests. Models the policy: a `run`
   that consults `allow_paths`/`allow_net`, records attempted reads/connects, and returns a
   `JailResult` with `denied=[…]` for any out-of-scope path or any connect when
   `allow_net=False`. Tests assert *folder-escape → Denial* and *undeclared-egress → Denial*
   **deterministically, with no kernel/OS dependency** — the same record-replay discipline
   as the rest of the suite (no live anything).
2. **Backend-conformance suite** — one parametrized test body run against `FakeJail` and
   (when available) the real backends, asserting identical *observable* policy: same denials,
   same taint round-trip, same registry rehydration. This is what stops the fake from drifting
   from reality.
3. **Real-sandbox integration tests (gated/skippable)** — a small set that actually invokes
   `bwrap` / `sandbox-exec` and proves the guarantee end-to-end: write outside `allow_paths`
   → blocked; `socket.connect()` with `allow_net=False` → blocked; both audited. Gated by
   `@pytest.mark.integration` + capability probes (`shutil.which("bwrap")`,
   kernel/Landlock check, `sys.platform=="darwin"`), **auto-skipped in CI** where the primitive
   is absent. Keeps `pytest -q` green and deterministic everywhere; the real escapes are still
   proven on a capable host / matrix runner.

## Alternatives rejected

- **WASM as the primary mechanism** — strongest *default* isolation and the only fully
  portable option, but server-side pyodide is unsupported and WASI CPython has no sockets/SSL
  and breaks C-extension nodes. It cannot run arbitrary host-side node Python today. Deferred
  as a possible *optional* backend behind the same `Jail` interface; the perf side stays in
  CRA-183.
- **Pure subprocess + drop-privileges + rlimits** — portable and dependency-free but provides
  **no real folder-scope and no egress block** without the OS primitives above; `rlimit` caps
  resources, not reach. Fails the only property that matters here. Retained only as the
  explicit, non-default `nojail` opt-out.
- **Docker / container-per-node** — heavyweight, needs a daemon + root/rootless setup, wrong
  altitude for a local-first tool, and not present on a plain `pip install`. (Same reasoning
  as ADR 0009 rejecting systemd/supervisord.) A later cloud/scale milestone may add a
  container backend behind `Jail`.
- **Hand-rolled seccomp without `bwrap`/Landlock** — re-implements what `bwrap` already does
  safely (user-ns juggling, mount setup); more attack surface, no portability gain. Use the
  vetted tool.
- **Single-OS-only (Linux-only or mac-only)** — both dev (macOS) and CI/deploy (Linux) are
  first-class; a one-OS jail would leave half the team's host-side code unjailed. The
  abstraction costs little and the OS matrix is fixed at macOS + Linux.

## Consequences

CRA-179 builds against `Jail` and `FakeJail` from day one — its acceptance tests assert
escape-blocking and taint/registry survival without ever spawning a real sandbox, while a
small gated integration suite proves the real primitive on a capable host. Adding a WASM or
container backend later, or Windows once a primitive exists, is a backend swap behind
`select_jail` — never a change to node code or the security properties. The deprecation risk
on `sandbox-exec` is the one watch item: if Apple removes it, the macOS backend swaps to an
App-Sandbox/XPC helper behind the same interface, with no caller change.

## Sources

- bubblewrap — <https://github.com/containers/bubblewrap> · nsjail — <https://github.com/google/nsjail>
- Landlock (kernel docs) — <https://docs.kernel.org/userspace-api/landlock.html> · <https://landlock.io/>
- macOS `sandbox-exec` deprecation-but-present — <https://news.ycombinator.com/item?id=44283454> ·
  <https://github.com/michaelneale/agent-seatbelt-sandbox> · ai-jail Seatbelt — <https://deepwiki.com/akitaonrails/ai-jail/4.5-macos:-seatbelt-sandboxing>
- OpenAI Codex cross-platform sandbox (`SandboxPolicy`/`SandboxManager`) — <https://codex.danielvaughan.com/2026/04/08/codex-sandbox-platform-implementation/> ·
  <https://deepwiki.com/openai/codex/5.6-sandboxing-implementation>
- WASM/WASI Python limits (no sockets, browser/Node-only pyodide) — <https://wasmlabs.dev/articles/python-wasm32-wasi/> ·
  <https://github.com/simonw/micropython-wasm> · <https://www.atlantbh.com/sandboxing-python-code-execution-with-wasm/>
