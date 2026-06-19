"""Tests for pipeline triggers (CRA-115)."""

from __future__ import annotations

import hashlib
import hmac

from crawfish.triggers import CronTrigger, WebhookTrigger, verify_webhook


def test_cron_trigger_describe_round_trips() -> None:
    trig = CronTrigger(schedule="0 * * * *")
    desc = trig.describe()
    assert desc["kind"] == "cron"
    assert desc["schedule"] == "0 * * * *"
    assert desc["id"] == trig.id


def test_webhook_trigger_describe_round_trips() -> None:
    trig = WebhookTrigger(path="/hooks/github", secret_ref="GITHUB_WEBHOOK_SECRET")
    desc = trig.describe()
    assert desc["kind"] == "webhook"
    assert desc["path"] == "/hooks/github"
    assert desc["secret_ref"] == "GITHUB_WEBHOOK_SECRET"


def test_webhook_trigger_stores_reference_not_value() -> None:
    secret_value = "super-secret-value"
    trig = WebhookTrigger(path="/hooks/x", secret_ref="MY_SECRET_ENV")
    # The reference is an env-var name, not the secret material itself.
    assert trig.secret_ref == "MY_SECRET_ENV"
    assert secret_value not in str(trig.describe())


def test_webhook_trigger_secret_ref_optional() -> None:
    trig = WebhookTrigger(path="/hooks/open")
    assert trig.secret_ref is None
    assert trig.describe()["secret_ref"] is None


def _sign(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def test_verify_webhook_accepts_correct_signature() -> None:
    secret = "shhh"
    payload = b'{"event": "push"}'
    assert verify_webhook(secret, payload, _sign(secret, payload)) is True


def test_verify_webhook_rejects_wrong_signature() -> None:
    secret = "shhh"
    payload = b'{"event": "push"}'
    assert verify_webhook(secret, payload, _sign("wrong", payload)) is False
    assert verify_webhook(secret, payload, "deadbeef") is False
