# Hard-blocker resolutions (decided autonomously — none handed to human)

The master prompt lists four hard blockers. Per the operator's standing instruction
("hand no decisions to me"), each is resolved here rather than escalated.

### HB-1 — Live credentials
**Status:** RESOLVED / present. `claude` CLI 2.1.187 on PATH; Milestone F was proven live
against real `claude -p` (haiku) with all six evidence items in `demo/triage-bot/RUNBOOK.md`.
The per-milestone live gate runs against the local `claude -p` backend (haiku for cost).
**Decision:** proceed with live acceptance each milestone; record evidence in RUNBOOK.

### HB-2 — F-6 / CRA-199 governance-only
**Status:** RESOLVED in Milestone F (shipped as the cost-model single-owner + composition law,
docs-forward). Its OPT-2 cost-owner note (CRA-220) is folded into Milestone 5.
**Decision:** treat as already-landed; no separate action; OPT-2 carries the cost-owner law.

### HB-3 — R2 / CRA-229 `craw prove --no-injection` (spike-gated moonshot)
**Plan:** timebox a spike in Milestone 7. If non-interference cannot be proven sound within
the box, ship the ALG-3 (CRA-231, pulled forward to M8) assembly-time fluid→static-sink
static-rejection fallback and flag R2 as a documented deferral. Never block the stack on it.
**Decision (pre-committed):** ALG-3 static rejection is the guaranteed floor; `prove` is best-effort.

### HB-4 — Security red flag (FLUID → instructions / consequential Sink / idempotency key)
**Pre-committed decision:** any such path **fails closed** at assembly time (ALG-3 semantics).
The security-review agent on every issue checks for this; if found, the safe (reject/attenuate)
branch is taken and recorded in that issue's decision file. Not escalated — resolved fail-closed.

---
## HB-3 RESOLVED (Milestone 7, CRA-229)
The R2 `craw prove --no-injection` spike concluded a SOUND full-graph non-interference proof
is not buildable today (the Definition exposes no serialized dataflow graph). Per the
pre-committed decision, shipped the **ALG-3 conservative static-rejection fallback**:
`guarantee="alg3-conservative-static-rejection"` — fail-closed, rejects any wiring where a
FLUID value can reach a consequential static-only slot (Sink target / idempotency key);
exits non-zero on a suspected path. Sound proof + ALG-7 conformance flagged best-effort/
deferred in CRA-229.md. The stack was NOT blocked. R3 (replay --swap) shipped concretely.
