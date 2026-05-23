# Requirements (from PRD-classified docs)

Extracted from docs classified as PRD. Each requirement has an ID `REQ-{slug}`, a `source:`, description, and acceptance criteria where the source provides them. PRD precedence among these (lower = higher): GRAND_PLAN.md, ORCHESTRATOR-ONEPAGER.md, ORCHESTRATOR-USER-STORIES.md all precedence 2.

The Orchestrator PRD trio (one-pager + user-stories) is an internally consistent product spec; GRAND_PLAN is the north-star vision the orchestrator funds. They do not contradict — orchestrator is explicitly "not a pivot away from the Grand Plan."

---

## From GRAND_PLAN.md (north-star vision, precedence 2)

source: /Users/nealkotval/crawfish/docs/roadmap/GRAND_PLAN.md

**REQ-agent-os-thesis** — Crawfish is the operating system for companies running on AI agents. The agent filesystem + librarian is the moat; the native orchestration runtime (§3.14) makes it defensible. *AC: org-level knowledge substrate + learning router that frontier vendors structurally cannot own.*

**REQ-tier1-personas** — Stage 1 features are graded against three Tier-1 personas whose love is required: solo startup founder, small company CEO, individual engineer at a small team. *AC: every Stage-1 feature lists which T1 personas it lights up.*

**REQ-linear-grade-board (§3.2)** — Native task board better than Linear for agent-native orgs: agents are first-class workspace members; cycles, epics, capability-matched routing, AI triage, auto-decomposition, linked-task graph, FTS5 structured search. *AC: drag tasks into cycles with budget rollup; epic auto-decomposes to approved subtask DAG; structured-query bar matches Linear idiom; agents bill as free members per Linear convention.*

**REQ-org-fs-librarian (§3.3 / §3.3.1)** — Org filesystem + knowledge librarian: per-source-class embedding spaces + contextual-bandit meta-router learning per-org which sources to consult per query type. LightRAG (SQLite + `sqlite-vec`, `transformers.js` MiniLM CPU), knowledge-graph extraction surfaced as navigable LLM Wiki. *AC: citations carry source_id/path_or_url/chunk_text/score/source_class/entity_path; `bandits.sqlite` + `feedback.jsonl` reward log; visible improvement-over-time graph.*

**REQ-knowledge-connectors (§3.3 connector list)** — Tier-1 connectors ship as benchmarked craws: Gmail/Outlook/IMAP, Slack/Discord/Teams, Notion/Confluence/Google Docs, GitHub/GitLab, Linear/Jira, local markdown vaults. *AC: OAuth/token in OS keychain; incremental watermark sync; per-source rate limits; never copies unauthorized content.*

**REQ-native-orchestration-runtime (§3.14)** — Native runtime with GOAP planner: plain-English goal → state-space A* → executable plan tree rendered in Plan tab, replans on state change. *AC: P5 ships minimum-viable runtime (capabilities 1–3); 4–8 deferred to P6+.*

**REQ-skills-backbone (§3.15)** — Vendor-neutral MIT skill collection in `~/.crawfish/skills/`, installable per-org or per-agent; diagnoses engine knows which skill should have been invoked on failure.

**REQ-craws-packaging (§3.16/§3.17)** — Craw manifest + kinds; per-craw defence policy (allow/deny file paths, network egress); signed-distribution marketplace (Stage 2). *AC: each craw benchmarked with verified token-per-doc cost.*

**REQ-test-visual-agents (§3.9)** — Test-generator agent + Playwright visual-auditor agent: per-PR run app, screenshot every route, diff baseline vs candidate, post visual changelog. Wraps existing `crawfish-opt` primitives.

**REQ-diagnoses-optimizers (§3.11)** — Diagnoses engine + optimizers as the cost-discipline pillar: cost-manager agent, dynamic model switching, regression alerts at 2σ.

**REQ-stage2-hosted (§4)** — Stage 2 (m9–m24): hosted everything, RL fine-tunes per org, invite employees/multi-user, 24/7 issue tracking, manager-grade employee analytics (privacy-respecting), org knowledge at scale, hybrid pricing.

**REQ-stage3-enterprise (§5)** — Stage 3 (m18+): compliance tier, audit export, attestation primitive, SSO/SAML/OIDC, on-prem, SOC2.

**Anti-goals (carry forward, all docs):** no auto-installation; no per-execution paywall on community craws; no enterprise paywalling of compliance.

---

## From ORCHESTRATOR-ONEPAGER.md (v1 wedge product spec, precedence 2)

source: /Users/nealkotval/crawfish/docs/roadmap/ORCHESTRATOR-ONEPAGER.md

**REQ-orch-wedge-product** — Cloud-hosted service: Linear/GitHub Issues in → auto-classify eligibility → dispatch to curated craws (impl + tester + reviewer) in isolated worktrees → CI-verified → checkpoint-gated PR out. *AC: ICP mid-market eng startups 10–50 engineers; eng leader buys, EM installs, IC reviews; hybrid seat+usage pricing (humans bill, agents free).*

**REQ-orch-wedge-task** — v1 narrows to "boring & bounded" tickets: dependency bumps with passing tests, test backfill, lint/dead-code cleanup, type-annotation backfill, low-risk CVE patches. *AC: machine-verifiable outcomes; low blast radius.*

**REQ-orch-success-metrics (12-month)** — 20 paying teams (avg 12 seats); ≥60% auto-classified tasks complete without escalation; ≤10% merged PRs need post-merge fix; <15min P50 ticket-to-draft-PR; 2x IC throughput on wedge class; cost per merged PR <30% of equivalent IC hour.

**REQ-orch-out-of-v1** — Deferred but on roadmap: customer-authored craws, marketplace, AI-generated craws, refactor/feature-class tasks, org-fs + librarian (stays roadmap), IDE, local Codespaces, Pilot Protocol, methodology packs, SSO/SAML, on-prem. Deferred forever in wedge: Slack-as-execution-surface, per-PR pricing, fully-autonomous PRs without checkpoints.

---

## From ORCHESTRATOR-USER-STORIES.md (MVP user stories, precedence 2)

source: /Users/nealkotval/crawfish/docs/roadmap/ORCHESTRATOR-USER-STORIES.md
Personas: VPE, EM, IC, PM, QA, PLAT, FIN, SEC. Stories tagged `[v1.5]`/`[deferred]` are out of v1.

**REQ-orch-onboarding (§1)** — GitHub-OAuth signup + workspace <90s; invite by email/domain with role at invite time; connect Linear (per-team toggle, webhooks) and GitHub App (per-repo PR-write toggle); detect GitHub Actions CI; 4-step empty-state walkthrough ending in a real sandbox-repo PR <10min; personal→team workspace conversion. *AC per story.* SSO/SAML deferred→v2.

**REQ-orch-craw-config (§2)** — Browse curated library (8–12 craws) with per-craw published bench (success rate, median tokens, latency, last update); 1-click install/uninstall (idempotent, preserves history); version pinning per-workspace (30-day rollback) + changelog before bump; routing rules (label→craw, first-match-wins, mandatory fallback); per-craw repo allow/deny (deny precedence); cross-repo drift indicator. Fork/customize is [v1.5]; marketplace submit deferred.

**REQ-orch-issue-intake (§3)** — Read Linear ticket <60s and decide craw-eligibility (webhook <10s, classifier <20s, decision as comment+label); per-workspace classifier config (threshold 0.0–1.0, default 0.7; below = "needs human review" label); per-ticket manual override (logged, persisted); "Craw will attempt this" comment with chosen craw + plan + decline button; confidence distribution over 7 days; GitHub Issues 5-min poll (dedup, rate-limit); label-allowlist-only mode (skips classifier, zero cost); re-run classifier on closed/old ticket.

**REQ-orch-plan-checkpoint (§4, gate 1)** — Pre-code plan posted as ticket comment, status "awaiting plan approval" (lists files, tests, expected diff size, est token cost); approve via 👍 reaction or dashboard button (logged); reject with one-line reason (returns to backlog); inline-edit plan + re-approve (original archived); per-label auto-approval (e.g. dep-bump); workspace policy "all plans require approval" vs "auto-approve unless risky" (craw can self-flag risky → always human); SLA notification (default 4h) + escalation to backup reviewer.

**REQ-orch-execution (§5)** — Durable workflow survives worker crash without double side-effects (idempotency keys); concurrency limit (default 5 workspace, 1 per repo) with queued position; cancel in-flight (<30s, worktree cleanup, partial PR closed, cost still billed); isolated git worktree per task (creation <5s); 1-click re-run (inherits plan+budget, fresh worktree, auto-disable after 3); per-task budget cap (default $5) + per-org daily cap (default $200) → pause + human approve; live queue with filters; idle auto-halt (default 5min, "stuck" label).

**REQ-orch-live-dashboard (§6)** — Open running task, real-time per-craw streaming tool-calls + reasoning (SSE, one row per craw, collapsed); multi-craw team view (renders "1 of 1" for single-craw v1); replay completed task from JSONL transcript; filter by repo/craw/status/reviewer (URL-persisted); org-wide rollup (30s refresh); per-step rationale + consulted trajectories; kill from any view.

**REQ-orch-ci-verification (§7)** — Customer CI (GitHub Actions) runs on craw PR (draft until CI completes); configurable required-jobs gate; on CI fail read log + fix up to N revisions (default 3, each a commit); after N fails halt + notify with log; regression guard (CI test-count drop fails gate, default on); optional test-generator + visual-auditor craws (GRAND_PLAN §3.9) as parallel CI checks; agent-authored tests labeled in PR + frontmatter.

**REQ-orch-merge-checkpoint (§8, gate 2)** — On CI pass, draft→ready-for-review with structured PR description; auto-assign reviewer (CODEOWNERS, fallback default); review as normal GitHub PR (zero Crawfish UI); single approval merges (respects branch protection, no force-merge); configurable N approvers (default 1 boring/2 risky); auto-close ticket on merge + Linear comment; reject PR halts craw + returns ticket to backlog.

**REQ-orch-pr-comment-loop (§9)** — @-mention `@crawfish-bot` re-engages (mention-only default); per-repo mode (mention-only/respond-to-all/off); "working on it" reply with est cost+ETA; per-PR cap (default 5 revisions / $10) → halt+notify; conflicting-reviewer detection → halt+ping human; out-of-scope honest "I can't address this without X"; audit entry per revision; `@crawfish-bot halt` stops <30s.

**REQ-orch-analytics (§10)** — Cost by workspace/repo/craw/ticket (daily, CSV export); compounding-factor metric (sub-agent/parent-useful tokens, GRAND_PLAN §3.6); per-craw stats (reuse `cli/projectctl/src/stats.ts`); per-engineer rollup (aggregates only, privacy contract §4.5); org-wide ROI proxy; FIN CSV billing export; per-ticket cycle-time vs human baseline. Forecast widget [v1.5].

**REQ-orch-failure-handling (§11)** — Failure surfaces in ticket + dashboard + optional email/Slack (one source of truth); failure taxonomy (7 categories) with trend lines; manual takeover (orchestrator detects human push + gracefully exits); auto-disable craw on failure spike (>50% in 24h on >5 attempts); weekly digest (opt-in); missing-capability failure recommends craw/skill.

**REQ-orch-billing-seats (§12)** — Stripe Connect, per-seat humans (agents free, GRAND_PLAN §3.2); seat usage vs plan with 80%/100% overage warnings; per-seat usage allowance (e.g. 100k tokens/mo, metered above, monthly reset, no rollover); hard monthly budget cap → pause new tasks + email; projected EOM cost; add/remove seats pro-rated; PDF invoices + email. Per-team envelopes [v1.5].

**REQ-orch-notifications (§13)** — In-app + email for plan-approval / PR-ready / stuck-on-owned-ticket (per-event settings); digest mode; mute per repo/ticket; one-way Slack webhook; billing-event notifications to billing email; escalation chain (24h unanswered → fallback). Discord/Teams/PagerDuty deferred→v2.

**REQ-orch-admin-audit-policy (§14)** — Immutable append-only audit log (JSONL, exportable) of governance actions; filter by actor/action/time/resource (90-day retention, configurable); RBAC (admin/member/viewer + documented matrix + per-resource override); workspace kill switch; per-craw file-path allow/deny (worktree-mount enforced); per-craw network egress allowlist (GitHub + LLM provider default, GRAND_PLAN §3.16); policy bundle per workspace (JSON, versioned with audit). SSO/SAML/OIDC/data-residency deferred→v2.

**REQ-orch-eval-quality (§15)** — Classifier accuracy (precision/recall/FPR over 30 days); label decisions correct/incorrect (per-workspace eval set, weekly re-eval); public per-craw bench scores; custom-benchmark dry-run (no PRs/comments); regression alert at 2σ (GRAND_PLAN §3.11). Tournament mode [v1.5].

**REQ-orch-integrations-edge (§16)** — Emergency GitHub App disable per repo (no config loss); detect direct push to craw branch → halt; GitHub outage/rate-limit → pause + auto-resume (exponential backoff); LLM provider outage → graceful halt + resume (durable engine); migrate GitHub Issues↔Linear preserving history; cancel subscription → 90-day export then deletion.
