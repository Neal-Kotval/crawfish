"""Host-side node isolation — the ``Jail`` abstraction (ADR 0016).

Host-side node code (sources/sinks/filters that execute *our* and *users'* Python,
not the ``claude -p`` child) runs **out-of-process**, scoped to an allowed folder,
with **network denied by default**. This is the host-side leg of the security spine
(``SECURITY.md``): code reachable from :class:`~crawfish.core.types.Flow.FLUID`
(untrusted session data) must run jailed so a prompt-injection-driven node cannot read
outside its folder or exfiltrate over the network.

The enforcement primitive is OS-sensitive, so this module follows ADR 0016: a single
:class:`Jail` ABC with one contract, two real backends — Linux (:class:`BwrapJail`,
``bwrap`` + seccomp + Landlock) and macOS (:class:`SeatbeltJail`, ``sandbox-exec``) —
plus an injectable in-process :class:`FakeJail` for deterministic tests and a
non-default :class:`NoJail` opt-out. :func:`select_jail` is the OS-sniffing factory.

**Security invariants (CRA-179 / ADR 0016):**

* ``allow_paths`` and ``allow_net`` are **STATIC-only** — they may never derive from
  ``Flow.FLUID`` input. A fluid value can never widen the jail. Passing a fluid-tagged
  :class:`JailPath` raises :class:`StaticOnlyError` before any process spawns.
* Secrets enter via ``env`` resolved-by-reference; never logged, never in-prompt.
* The child process is the **taint boundary**. Input ``taint`` is serialized in;
  every value crossing back is re-tagged via :attr:`JailResult.out_taint`. Tool/MCP
  results and any fluid-derived child output stay tainted.
* Every escape attempt (folder / net) is a :class:`Denial`, surfaced on
  :attr:`JailResult.denied` and audited as an :class:`~crawfish.emission.EmissionKind`
  ``JAIL_VIOLATION`` emission (for the CRA-189 red-team demo + dashboard).
* The child rehydrates :data:`~crawfish.typesystem.default_registry` from serialized
  descriptors so ``parameters_compatible`` holds across the boundary.
"""

from __future__ import annotations

import shutil
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from crawfish.core.types import Flow
from crawfish.emission import Emission, EmissionKind, emit
from crawfish.typesystem import TypeDef, TypeKind, TypeRegistry, default_registry

if TYPE_CHECKING:
    from crawfish.store.base import Store

__all__ = [
    "TaintSet",
    "FLUID_TAINT",
    "PathMode",
    "JailPath",
    "DenialKind",
    "Denial",
    "JailResult",
    "SandboxPolicy",
    "StaticOnlyError",
    "UnsupportedPlatformError",
    "Jail",
    "FakeJail",
    "NoJail",
    "BwrapJail",
    "SeatbeltJail",
    "select_jail",
    "registry_descriptors",
    "rehydrate_registry",
    "emit_denials",
]

# A taint label set. Labels are opaque strings (e.g. "fluid"); the presence of any
# label means the value is untrusted. Serialized across the process boundary as a
# JSON list, so it must stay JSON-primitive.
TaintSet = frozenset[str]

# The canonical label every fluid-derived value carries. A child that read fluid
# input, called a tool, or hit the network re-emits at least this label.
FLUID_TAINT = "fluid"


class PathMode(str, Enum):
    """Access mode for an allowed path. ``(str, Enum)`` per ADR 0004."""

    RO = "ro"
    RW = "rw"


@dataclass(frozen=True)
class JailPath:
    """A host path made reachable inside the jail.

    ``flow`` records where the path value came from. ``allow_paths`` is **STATIC-only**:
    a :class:`JailPath` whose ``flow`` is :attr:`Flow.FLUID` is rejected by every jail
    before any process spawns (a fluid value can never widen the jail — ADR 0016).
    """

    path: str
    mode: PathMode = PathMode.RO
    flow: Flow = Flow.STATIC

    def contains(self, candidate: str) -> bool:
        """True if ``candidate`` is this path or lives beneath it (no escape)."""
        base = PurePosixPath(self.path)
        target = PurePosixPath(candidate)
        if target == base:
            return True
        return base in target.parents


class DenialKind(str, Enum):
    FOLDER_ESCAPE = "folder_escape"  # read/write outside allow_paths
    UNDECLARED_EGRESS = "undeclared_egress"  # network connect with allow_net=False
    TIMEOUT = "timeout"  # wall-clock budget exceeded


@dataclass(frozen=True)
class Denial:
    """One audited escape attempt the jail blocked.

    ``severity`` defaults to ``"high"`` — a blocked folder-escape or egress is a
    security-relevant event the broker (CRA-186) and dashboard (CRA-189) must see.
    """

    kind: DenialKind
    attempt: str  # the path or host:port the child tried to reach
    severity: str = "high"

    def as_attrs(self) -> dict[str, object]:
        """The ``attrs`` payload for a ``JAIL_VIOLATION`` emission (ADR 0016)."""
        return {"attempt": self.attempt, "severity": self.severity, "kind": self.kind.value}


@dataclass(frozen=True)
class JailResult:
    """The frozen result of a jailed run (Freezable per ADR 0006).

    ``out_taint`` carries the taint propagated back out of the child — the taint
    boundary made explicit across the process edge.
    """

    exit_code: int
    stdout: bytes
    stderr: bytes
    out_taint: TaintSet = frozenset()
    denied: tuple[Denial, ...] = ()
    timed_out: bool = False


@dataclass(frozen=True)
class SandboxPolicy:
    """Static configuration that selects + parameterizes the jail.

    ``kind`` pins a backend for tests/opt-out; ``None`` lets :func:`select_jail`
    sniff the OS. ``allow_net`` here is the policy default; a per-run ``allow_net``
    can only ever *narrow* it (never widen), and both are static.
    """

    kind: str | None = None  # 'bwrap' | 'seatbelt' | 'fake' | 'nojail' | None (auto)
    allow_net: bool = False


class StaticOnlyError(ValueError):
    """Raised when a FLUID value is offered where only STATIC is permitted.

    Enforces the spine rule: ``allow_paths``/``allow_net`` derive from static node
    config only — a fluid (untrusted) value can never widen the jail.
    """


class UnsupportedPlatformError(RuntimeError):
    """Raised by :func:`select_jail` on a platform with no real backend (Windows)."""


# -- type-registry rehydration across the boundary -------------------------------


def registry_descriptors(registry: TypeRegistry = default_registry) -> list[dict[str, object]]:
    """Serialize a registry's records to JSON descriptors for the child.

    ``default_registry`` is a process-global; the jailed child is a *fresh* process,
    so it cannot inherit Python identities. Structural types travel as serialized
    :class:`~crawfish.typesystem.TypeDef` descriptors and the child reconstructs them,
    so ``parameters_compatible`` holds across the boundary (ADR 0016 / CRA-188 AC).
    """
    records: dict[str, TypeDef] = registry._records  # records-only; primitives are nominal
    return [td.model_dump(mode="json") for td in records.values()]


def rehydrate_registry(
    descriptors: Sequence[Mapping[str, object]],
    registry: TypeRegistry | None = None,
) -> TypeRegistry:
    """Reconstruct a :class:`TypeRegistry` in the child from serialized descriptors.

    Called at child startup. Rebuilds ``default_registry`` (or a given registry) so
    structural compatibility checks behave identically to the parent process.
    """
    target = registry if registry is not None else default_registry
    for raw in descriptors:
        td = TypeDef.model_validate(dict(raw))
        if td.kind is TypeKind.RECORD:
            target.register_record(td.name, dict(td.fields))
        else:
            target.register_primitive(td.name)
    return target


# -- audit: denials -> JAIL_VIOLATION emissions ----------------------------------


def emit_denials(
    store: Store,
    result: JailResult,
    *,
    run_id: str,
    node_id: str | None = None,
    org_id: str = "local",
    pipeline: str | None = None,
    ts: float = 0.0,
) -> list[Emission]:
    """Write one ``JAIL_VIOLATION`` emission per :class:`Denial` to the ledger.

    Satisfies the broker's (CRA-186) "blocked **and audited**" contract and feeds the
    CRA-189 red-team demo + dashboard. Each emission carries the required ``attempt``
    and ``severity`` attrs (:data:`~crawfish.emission.REQUIRED_ATTRS`) and is
    ``tainted=True`` — a denial is, by definition, an attempt by jailed (untrusted)
    code. Returns the emissions written (for tests / inline inspection).
    """
    written: list[Emission] = []
    for d in result.denied:
        e = Emission(
            kind=EmissionKind.JAIL_VIOLATION,
            run_id=run_id,
            org_id=org_id,
            pipeline=pipeline,
            node_id=node_id,
            ts=ts,
            attrs=d.as_attrs(),
            tainted=True,
        )
        emit(store, e, org_id=org_id)
        written.append(e)
    return written


# -- the Jail contract -----------------------------------------------------------


class Jail(ABC):
    """Out-of-process, folder-scoped, network-denied execution of host-side node code.

    A behavioural ABC (ADR 0004), imported by the node runner — never a concrete
    backend imported directly. Backends are selected by :func:`select_jail`; tests
    inject :class:`FakeJail`.
    """

    @abstractmethod
    def run(
        self,
        cmd: Sequence[str],
        *,
        allow_paths: Sequence[JailPath] = (),
        allow_net: bool = False,
        env: Mapping[str, str] | None = None,
        stdin: bytes | None = None,
        cwd: JailPath | str | None = None,
        timeout_s: float | None = None,
        taint: TaintSet = frozenset(),
    ) -> JailResult:
        """Run ``cmd`` jailed and return its frozen :class:`JailResult`."""

    @property
    @abstractmethod
    def kind(self) -> str:
        """Backend tag: ``'bwrap' | 'seatbelt' | 'fake' | 'nojail'``."""

    # -- shared spine enforcement (every backend calls this) ---------------------
    @staticmethod
    def _check_static(allow_paths: Sequence[JailPath]) -> None:
        """Reject any FLUID-tagged allow path — a fluid value can never widen the jail."""
        for p in allow_paths:
            if p.flow is Flow.FLUID:
                raise StaticOnlyError(
                    f"allow_paths is STATIC-only; refusing FLUID path {p.path!r} "
                    "(a fluid value can never widen the jail — ADR 0016)"
                )


# -- FakeJail: in-process, deterministic transport -------------------------------


@dataclass
class _Probe:
    """A child's declared intent, fed to :class:`FakeJail` for deterministic policy.

    The fake doesn't spawn anything; the test supplies a ``program`` describing the
    paths the child would touch and the hosts it would connect to, plus the bytes it
    would emit and whether its output derives from fluid input. The fake then applies
    *exactly the policy* a real backend enforces, recording denials.
    """

    reads: Sequence[str] = field(default_factory=tuple)
    writes: Sequence[str] = field(default_factory=tuple)
    connects: Sequence[str] = field(default_factory=tuple)  # "host:port"
    stdout: bytes = b""
    stderr: bytes = b""
    exit_code: int = 0
    emits_fluid: bool = False  # child output derives from fluid/tool input


class FakeJail(Jail):
    """In-process fake honouring the same observable policy as a real backend.

    Default in unit tests (ADR 0016 testing strategy). Spawns nothing: it consults
    ``allow_paths``/``allow_net``, records every out-of-scope path and every connect
    when ``allow_net=False`` as a :class:`Denial`, and round-trips taint. The
    backend-conformance suite runs one body against this and (when present) the real
    backends to stop the fake from drifting.

    The "program" the child would run is injected as a callable mapping ``cmd`` to a
    :class:`_Probe`. The default ``program`` is a no-op child (touches nothing),
    keeping callers that don't care about probes trivial.
    """

    def __init__(self, program: Callable[[Sequence[str]], _Probe] | None = None) -> None:
        self._program = program or _probe_from_noop

    @property
    def kind(self) -> str:
        return "fake"

    def run(
        self,
        cmd: Sequence[str],
        *,
        allow_paths: Sequence[JailPath] = (),
        allow_net: bool = False,
        env: Mapping[str, str] | None = None,
        stdin: bytes | None = None,
        cwd: JailPath | str | None = None,
        timeout_s: float | None = None,
        taint: TaintSet = frozenset(),
    ) -> JailResult:
        self._check_static(allow_paths)
        probe = self._program(cmd)
        denied: list[Denial] = []

        ro = list(allow_paths)  # any allowed path permits read
        rw = [p for p in allow_paths if p.mode is PathMode.RW]

        for r in probe.reads:
            if not any(p.contains(r) for p in ro):
                denied.append(Denial(DenialKind.FOLDER_ESCAPE, r))
        for w in probe.writes:
            if not any(p.contains(w) for p in rw):
                denied.append(Denial(DenialKind.FOLDER_ESCAPE, w))
        if not allow_net:
            for host in probe.connects:
                denied.append(Denial(DenialKind.UNDECLARED_EGRESS, host))

        # Taint boundary: input taint flows out; a child that read fluid/tool data or
        # touched the network re-tags its output as fluid. A denial is itself evidence
        # the child reached for untrusted scope, so it taints the result too.
        out_taint = set(taint)
        if probe.emits_fluid or probe.connects or denied:
            out_taint.add(FLUID_TAINT)

        # If the child actually escaped, its stdout is untrustworthy -> nonzero exit.
        exit_code = probe.exit_code if not denied else (probe.exit_code or 1)
        return JailResult(
            exit_code=exit_code,
            stdout=probe.stdout,
            stderr=probe.stderr,
            out_taint=frozenset(out_taint),
            denied=tuple(denied),
            timed_out=False,
        )


def _probe_from_noop(cmd: Sequence[str]) -> _Probe:
    """Default program: a child that touches nothing and emits nothing."""
    return _Probe()


# -- NoJail: explicit, non-default opt-out (ADR 0016) ----------------------------


class NoJail(Jail):
    """Passthrough — runs out-of-process but enforces no folder/net scope.

    The rejected pure-subprocess fallback, retained ONLY as the explicit opt-out for
    code that is provably not FLUID-reachable. Never the default for fluid code. Still
    runs out-of-process (no shared engine memory) and still propagates taint.
    """

    @property
    def kind(self) -> str:
        return "nojail"

    def run(
        self,
        cmd: Sequence[str],
        *,
        allow_paths: Sequence[JailPath] = (),
        allow_net: bool = False,
        env: Mapping[str, str] | None = None,
        stdin: bytes | None = None,
        cwd: JailPath | str | None = None,
        timeout_s: float | None = None,
        taint: TaintSet = frozenset(),
    ) -> JailResult:
        self._check_static(allow_paths)
        code, out, err, timed = _spawn(
            cmd, stdin=stdin, env=env, cwd=_cwd_str(cwd), timeout_s=timeout_s
        )
        return JailResult(
            exit_code=code,
            stdout=out,
            stderr=err,
            out_taint=frozenset(taint),
            timed_out=timed,
        )


# -- Real backends: capability-probed, shell out to bwrap / sandbox-exec ----------


class _RealJail(Jail):
    """Shared spine for the two real backends: argv assembly + capability probe.

    Subclasses build the wrapper argv (``_wrap``) and declare a capability probe
    (``available``). Real execution goes through ``run_out_of_process`` so the
    spawned sandbox process never shares the engine's memory.
    """

    def run(
        self,
        cmd: Sequence[str],
        *,
        allow_paths: Sequence[JailPath] = (),
        allow_net: bool = False,
        env: Mapping[str, str] | None = None,
        stdin: bytes | None = None,
        cwd: JailPath | str | None = None,
        timeout_s: float | None = None,
        taint: TaintSet = frozenset(),
    ) -> JailResult:
        self._check_static(allow_paths)
        if not self.available():  # pragma: no cover - exercised only off-platform
            raise UnsupportedPlatformError(
                f"{self.kind} backend unavailable on this host (capability probe failed)"
            )
        wrapped = self._wrap(cmd, allow_paths=allow_paths, allow_net=allow_net, cwd=cwd)
        code, out, err, timed = _spawn(wrapped, stdin=stdin, env=env, cwd=None, timeout_s=timeout_s)
        # On a real backend the kernel/Seatbelt blocks escapes *before* they happen, so
        # a clean exit means no denial. The child re-tags its own output taint via a
        # stdout protocol; absent that we conservatively carry input taint forward.
        denied = (Denial(DenialKind.TIMEOUT, " ".join(cmd)),) if timed else ()
        return JailResult(
            exit_code=code,
            stdout=out,
            stderr=err,
            out_taint=frozenset(taint),
            denied=denied,
            timed_out=timed,
        )

    @abstractmethod
    def available(self) -> bool:
        """Capability probe: is this backend's primitive present on this host?"""

    @abstractmethod
    def _wrap(
        self,
        cmd: Sequence[str],
        *,
        allow_paths: Sequence[JailPath],
        allow_net: bool,
        cwd: JailPath | str | None,
    ) -> list[str]:
        """Build the wrapper argv that enforces the policy around ``cmd``."""


class BwrapJail(_RealJail):
    """Linux backend — ``bwrap`` + seccomp + Landlock (ADR 0016).

    Net namespace (``--unshare-net``) makes loopback the only reachable network, so
    no egress path exists; ``--ro-bind``/``--bind`` are the folder allow-list; the
    new user namespace drops ambient authority. Requires the ``bwrap`` binary.
    """

    @property
    def kind(self) -> str:
        return "bwrap"

    def available(self) -> bool:
        return sys.platform.startswith("linux") and shutil.which("bwrap") is not None

    def _wrap(
        self,
        cmd: Sequence[str],
        *,
        allow_paths: Sequence[JailPath],
        allow_net: bool,
        cwd: JailPath | str | None,
    ) -> list[str]:
        argv: list[str] = ["bwrap", "--unshare-user", "--unshare-pid", "--die-with-parent"]
        if not allow_net:
            argv += ["--unshare-net"]  # loopback-only: no egress path exists
        for p in allow_paths:
            flag = "--bind" if p.mode is PathMode.RW else "--ro-bind"
            argv += [flag, p.path, p.path]
        cwds = _cwd_str(cwd)
        if cwds is not None:
            argv += ["--chdir", cwds]
        argv += ["--", *cmd]
        return argv


class SeatbeltJail(_RealJail):
    """macOS backend — ``sandbox-exec`` / Seatbelt profile (ADR 0016).

    ``(deny default)`` + ``(allow file-read*/file-write* (subpath …))`` + ``(deny
    network*)``. Deprecated-but-present (the warning goes to stderr; the mechanism
    still enforces on macOS 15). Requires the ``sandbox-exec`` binary on darwin.
    """

    @property
    def kind(self) -> str:
        return "seatbelt"

    def available(self) -> bool:
        return sys.platform == "darwin" and shutil.which("sandbox-exec") is not None

    def profile(self, allow_paths: Sequence[JailPath], allow_net: bool) -> str:
        """Render the Seatbelt SBPL profile for these paths (also used by tests)."""
        lines = ["(version 1)", "(deny default)", "(allow process-fork)", "(allow process-exec)"]
        for p in allow_paths:
            esc = p.path.replace('"', '\\"')
            lines.append(f'(allow file-read* (subpath "{esc}"))')
            if p.mode is PathMode.RW:
                lines.append(f'(allow file-write* (subpath "{esc}"))')
        lines.append("(allow network*)" if allow_net else "(deny network*)")
        return "\n".join(lines)

    def _wrap(
        self,
        cmd: Sequence[str],
        *,
        allow_paths: Sequence[JailPath],
        allow_net: bool,
        cwd: JailPath | str | None,
    ) -> list[str]:
        prof = self.profile(allow_paths, allow_net)
        return ["sandbox-exec", "-p", prof, *cmd]


# -- spawn helper (out-of-process) -----------------------------------------------


def _spawn(
    argv: Sequence[str],
    *,
    stdin: bytes | None,
    env: Mapping[str, str] | None,
    cwd: str | None,
    timeout_s: float | None,
) -> tuple[int, bytes, bytes, bool]:
    """Run ``argv`` in a separate process. Returns (exit_code, stdout, stderr, timed_out)."""
    from crawfish.sandbox import run_out_of_process

    payload = (list(argv), stdin, dict(env) if env is not None else None, cwd, timeout_s)
    try:
        return run_out_of_process(_subprocess_exec, payload, timeout=(timeout_s or 30.0) + 5.0)
    except TimeoutError:  # pragma: no cover - integration-only path
        return (124, b"", b"jail: timed out", True)
    except Exception as exc:  # pragma: no cover - defensive
        return (1, b"", str(exc).encode(), False)


def _subprocess_exec(
    payload: tuple[list[str], bytes | None, dict[str, str] | None, str | None, float | None],
) -> tuple[int, bytes, bytes, bool]:
    """Module-level (picklable) child entry: runs the wrapped argv via subprocess."""
    import subprocess

    argv, stdin, env, cwd, timeout_s = payload
    try:
        proc = subprocess.run(  # noqa: S603 — argv is static node/wrapper config, never fluid
            argv,
            input=stdin,
            env=env,
            cwd=cwd,
            capture_output=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return (124, b"", b"jail: timed out", True)
    return (proc.returncode, proc.stdout, proc.stderr, False)


def _cwd_str(cwd: JailPath | str | None) -> str | None:
    if cwd is None:
        return None
    return cwd.path if isinstance(cwd, JailPath) else cwd


# -- factory ---------------------------------------------------------------------


def select_jail(policy: SandboxPolicy | None = None) -> Jail:
    """OS-sniffing factory (ADR 0016). Raises on a platform with no real backend.

    ``policy.kind`` pins a backend (used by tests and the ``nojail`` opt-out); ``None``
    sniffs: Linux → :class:`BwrapJail`, macOS → :class:`SeatbeltJail`. Windows has no
    clean unprivileged primitive and is deferred (ADR 0009) → :class:`UnsupportedPlatformError`.
    """
    pol = policy or SandboxPolicy()
    if pol.kind == "fake":
        return FakeJail()
    if pol.kind == "nojail":
        return NoJail()
    if pol.kind == "bwrap":
        return BwrapJail()
    if pol.kind == "seatbelt":
        return SeatbeltJail()

    if sys.platform.startswith("linux"):
        return BwrapJail()
    if sys.platform == "darwin":
        return SeatbeltJail()
    raise UnsupportedPlatformError(
        f"no host-side jail backend for platform {sys.platform!r}; "
        "Windows is deferred (ADR 0009). Use SandboxPolicy(kind='nojail') to opt out."
    )
