"""``craw code lint`` — the secret-shaped-literal lint (CRA-276).

Templates teach shape. A template (or an agent-edited file) that models an *inline* secret
or a fluid destination teaches Claude the wrong shape, and an injected agent will copy it
(RFC §12.2). The mitigation is reference-only credential slots (an env-var *name*, never a
value) enforced by a **pure, AST-/regex-free** scan that **fails closed** (exit 6) on a
high-entropy literal or a known-credential shape assigned to a secret-named variable.

This module is the canonical home for the detector (:func:`secret_shaped_findings`) — both
the standalone ``craw code lint`` verb *and* the post-write gate inside ``craw code new``
call it, so teaching and enforcement share one detector. **Detector parity** with
:data:`crawfish.secrets._PATTERNS` (the :class:`~crawfish.secrets.ScrubbingStore` redaction
set) is the load-bearing property: a template that passes lint can never trip scrub at run
time. The lint output is itself scrubbed — a finding never echoes the matched secret raw (a
finding that printed the literal would be a leak, CRA-276 security note).

A self-registering verb (``register(subparsers)``).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from crawfish.code import (
    EXIT_OK,
    SCHEMA_VERSIONS,
    ErrorCode,
    emit_error,
    emit_json,
)

VERB_NAME = "lint"

# This verb's --json schema, seeded here (not by editing the shared registry).
SCHEMA_VERSIONS.setdefault("code.lint", (1, 0))  # type: ignore[attr-defined]

#: The redaction marker the finding carries — never the matched literal (CRA-276).
REDACTED = "***REDACTED***"

#: The spec's enumerated credential shapes beyond the shared ScrubbingStore set: an AWS
#: access-key id, and any long literal assigned to a credential-shaped variable name.
_AWS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")
_SECRET_ASSIGN = re.compile(
    r"""(?ix)                                                # case-insensitive, verbose
    \b(token|secret|password|passwd|api[_-]?key|auth)\b      # a credential-shaped name
    \s*[:=]\s*                                               # = or :
    ['"]([A-Za-z0-9+/=_\-]{20,})['"]                         # a long literal value (b64-incl)
    """
)
#: An UPPER_SNAKE_CASE value is an env-var *name* reference (the correct shape), not a
#: secret value — ``auth="GITHUB_TOKEN"`` must never be a finding.
_ENV_REF = re.compile(r"[A-Z][A-Z0-9_]*")

#: Files the lint scans: emitted/edited Python and markdown (the template surface).
_LINT_SUFFIXES = {".py", ".md"}


def secret_shaped_findings(text: str, *, path: str = "") -> list[dict[str, object]]:
    """Pure scan of ``text`` for inline-credential shapes; findings carry a REDACTED value.

    Shares :data:`crawfish.secrets._PATTERNS` (the ScrubbingStore detector — detector
    parity) plus the AWS-key and secret-named-assignment shapes. Each finding names the line
    and (when given) the path; the matched value is **never** echoed raw. Pure: no network,
    no model, no clock.
    """
    from crawfish.secrets import _PATTERNS

    findings: list[dict[str, object]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        hit = False
        for pat in (*_PATTERNS, _AWS_KEY):
            if pat.search(line):
                hit = True
                break
        if not hit:
            m = _SECRET_ASSIGN.search(line)
            # A long value that is an all-caps env-var NAME reference is the correct shape
            # (auth="GITHUB_TOKEN"); only a non-reference literal is a finding.
            if m is not None and not _ENV_REF.fullmatch(m.group(2)):
                hit = True
        if hit:
            finding: dict[str, object] = {
                "line": lineno,
                "kind": "inline_secret",
                "match_redacted": REDACTED,
                "remediation": 'reference by env-var name, e.g. auth="GITHUB_TOKEN"',
            }
            if path:
                finding["path"] = path
            findings.append(finding)
    return findings


def lint_tree(root: Path) -> list[dict[str, object]]:
    """Scan every lintable file under ``root`` (skipping generated/vendor dirs)."""
    findings: list[dict[str, object]] = []
    skip = {".crawfish", ".claude", "__pycache__", ".venv", ".git", "node_modules"}
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in _LINT_SUFFIXES:
            continue
        if any(part in skip for part in f.relative_to(root).parts):
            continue
        # .env.example documents references-only by design — it is the reference template,
        # never an inline secret, so it is out of scope for the inline-secret scan.
        if f.name == ".env.example":
            continue
        findings.extend(secret_shaped_findings(f.read_text(), path=str(f.relative_to(root))))
    return findings


def register(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register ``craw code lint`` on the ``code`` subparser group."""
    from crawfish.code.cli import add_common_args

    p = subparsers.add_parser(VERB_NAME, help="scan for inline-secret shapes (fail closed)")
    p.add_argument("--dir", default=".", help="project directory (default: cwd)")
    add_common_args(p)
    p.set_defaults(func=_cmd_lint)


def _cmd_lint(args: argparse.Namespace) -> int:
    """Scan the tree; emit ``craw.code.lint.v1``; fail closed (exit 6) on any finding."""
    as_json: bool = getattr(args, "as_json", False)
    org: str = getattr(args, "org", "local")
    findings = lint_tree(Path(args.dir))

    if findings:
        # A hit fails closed (spec exit 6, mapped onto the shared usage family exit 2 with
        # the spec exit + findings in the detail). The findings are already redacted.
        return emit_error(
            ErrorCode.USAGE,
            remediation="inline-credential shape(s) found; reference secrets by env-var name "
            '(auth="GITHUB_TOKEN")',
            detail={"exit": 6, "reason": "secret_shaped", "verdict": "fail", "findings": findings},
            as_json=as_json,
        )

    payload: dict[str, object] = {"findings": [], "verdict": "clean"}
    if as_json:
        emit_json("code.lint", payload, org=org)
    else:
        print("lint: clean (no inline-secret shapes found)")
    return EXIT_OK
