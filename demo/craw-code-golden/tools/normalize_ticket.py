"""normalize_ticket — the callable name MUST equal the filename stem (loader contract).

Host-side tool code runs out-of-process at run time, and taint propagates: ``ticket_body``
is FLUID (untrusted) data, so its normalized form stays tainted and can never silently
become a static sink target or an idempotency key.
"""

from __future__ import annotations


def normalize_ticket(ticket_body: str) -> str:
    """Strip and lower-case a ticket body. The argument is FLUID (untrusted) data."""
    return ticket_body.strip().lower()
