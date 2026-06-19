"""A tool: filename stem `open_pr` is the tool name (no registration)."""

from __future__ import annotations


def open_pr(title: str, body: str) -> str:
    return f"opened PR: {title}"
