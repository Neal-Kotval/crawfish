# lang_notes — autonomous decision log

Every architectural or security fork encountered while building **The Agent Language**
(milestones 1→S, CRA-202..242) is decided autonomously and recorded here. **No decision is
handed back to the human.** This folder is the running ledger of *why* the language is shaped
the way it is, alongside the formal ADRs in `docs/architecture/decisions/`.

## Conventions

- One file per issue's decisions: `lang_notes/CRA-<n>-decisions.md`.
- Each issue gets a paired **architecture review** and **security review** (specialist
  subagents) before its code integrates into the milestone branch. Their verdicts + every
  fork they resolve are captured in that issue's file.
- Milestone-level decisions (wave splits, shared-file resolutions, deferrals) go in
  `lang_notes/M<n>-milestone.md`.
- Hard-blocker resolutions (live creds, F-6 governance, R2 spike, any FLUID→sink red flag)
  are recorded in `lang_notes/HARD-BLOCKERS.md` with the chosen path and rationale.
- When a fork is load-bearing for the spine, also mint a formal ADR and cross-link it here.

## Decision record format

```
### D<seq> — <short title>   (issue CRA-<n>, <arch|security|both>)
**Fork:** <the choice that had ≥2 viable options>
**Options:** <A / B / C, one line each>
**Decision:** <chosen>  **Rationale:** <why, tied to the thesis / spine>
**Rejected because:** <one line per rejected option>
**Spine impact:** <type-compat / tenancy / fluid-boundary / versioning / cost / none>
```

## Thesis being upheld (the lens for every decision)

One stochastic primitive (the model call); everything else is deterministic, typed,
versioned, taint-tracked Python. `mutable` is train/eval mode. Only a frozen, content-hashed
Definition may fire a consequential Sink. `Flow.FLUID` is untrusted data, never instructions,
never a static Sink target / idempotency key.
