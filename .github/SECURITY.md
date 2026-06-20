# Security Policy

Crawfish runs agent code over your data and touches credentials, so we take
security reports seriously. This document is the **disclosure policy** — how to
report a vulnerability privately. It is distinct from
[`docs/architecture/SECURITY.md`](../docs/architecture/SECURITY.md), which is the
framework's *threat model* (the security spine: the fluid/static trust boundary,
static-only sink targets, secrets-by-reference, out-of-process node execution).

## Reporting a vulnerability

**Please do not open a public issue for security vulnerabilities.** Public
disclosure before a fix puts every user at risk.

Report privately through either channel:

1. **GitHub private vulnerability reporting** (preferred) — go to the
   repository's **Security** tab → **Report a vulnerability**. This opens a
   private advisory visible only to you and the maintainers.
2. **Email** — **`neal.kotval@gmail.com`**. Encrypt if you can; ask for a key if needed.

Include, as far as you can: the affected version/commit, a description of the
issue and its impact, and a minimal reproduction (proof-of-concept, steps, or a
failing test). If the issue concerns the trust boundary — e.g. a fluid input
reaching the model as an instruction, a sink target being redirected by
model-influenced data, or a secret leaking into config/logs/prompts — say so
explicitly; those are our highest-severity classes.

## What to expect

| Stage | Target |
| --- | --- |
| Acknowledge your report | within **3 business days** |
| Initial assessment / triage | within **7 business days** |
| Fix + coordinated disclosure | severity-dependent; we'll keep you updated |

We practice **coordinated disclosure**: we'll work with you on a fix and a
disclosure timeline, credit you in the advisory and release notes (unless you
prefer to remain anonymous), and ask that you give us a reasonable window to ship
a fix before any public discussion.

## Supported versions

Crawfish is pre-1.0. Security fixes land on the **latest released minor** and
`main`. Older versions are not patched — please upgrade to the latest release.

| Version | Supported |
| --- | --- |
| latest `0.x` release | ✅ |
| `main` (unreleased) | ✅ |
| older releases | ❌ (upgrade) |

## Scope

In scope: the `crawfish` package, the `craw` CLI, the runtime/store/artifact
seams, and the security spine described in the threat model. Out of scope:
vulnerabilities in your own pipeline definitions, third-party connectors not
maintained in this repo, and issues that require a pre-compromised host.

Thank you for helping keep Crawfish and its users safe.
