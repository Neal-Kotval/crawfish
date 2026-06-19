"""Pipeline triggers: cron + webhook (CRA-115).

A pipeline declares *how* it fires. Beyond cron (time-based polling), a webhook
trigger is a true push: an HTTP endpoint enqueues a run and carries the payload,
no polling required. Webhook secrets are held **by reference** — the name of an
environment variable, never an inline value — so secrets never enter the manifest
or any serialized description. :func:`verify_webhook` does constant-time
HMAC-SHA256 verification of inbound payloads.
"""

from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod

from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue

__all__ = [
    "Trigger",
    "CronTrigger",
    "WebhookTrigger",
    "verify_webhook",
]


class Trigger(ABC):
    """Base for anything that can fire a pipeline run (CRA-115)."""

    id: str
    kind: str

    @abstractmethod
    def describe(self) -> dict[str, JSONValue]:
        """Return a JSON-serialisable description of this trigger (CRA-115)."""
        raise NotImplementedError


class CronTrigger(Trigger):
    """Fire a run on a cron ``schedule`` (CRA-115)."""

    def __init__(self, schedule: str) -> None:
        self.id = new_id()
        self.kind = "cron"
        self.schedule = schedule

    def describe(self) -> dict[str, JSONValue]:
        """Round-trippable description: kind + schedule (CRA-115)."""
        return {"id": self.id, "kind": self.kind, "schedule": self.schedule}


class WebhookTrigger(Trigger):
    """Fire a run from an inbound HTTP POST to ``path`` (CRA-115).

    ``secret_ref`` is the *name* of an environment variable holding the shared
    secret, never the secret value itself, so it is safe to serialise.
    """

    def __init__(self, path: str, secret_ref: str | None = None) -> None:
        self.id = new_id()
        self.kind = "webhook"
        self.path = path
        self.secret_ref = secret_ref

    def describe(self) -> dict[str, JSONValue]:
        """Round-trippable description; carries the secret *reference* only (CRA-115)."""
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "secret_ref": self.secret_ref,
        }


def verify_webhook(secret: str, payload: bytes, signature: str) -> bool:
    """Verify an inbound webhook ``signature`` against ``payload`` (CRA-115).

    Computes ``HMAC-SHA256(secret, payload)`` as lowercase hex and compares it to
    ``signature`` in constant time to avoid timing oracles. The caller resolves
    ``secret`` from the trigger's ``secret_ref`` environment variable.
    """
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
