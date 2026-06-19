"""Tests for pipeline triggers (CRA-115)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

import pytest

from crawfish.triggers import Cron, CronSchedule, CronTrigger, WebhookTrigger, verify_webhook


def _dt(y: int = 2026, mo: int = 1, d: int = 1, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_cron_daily_at_8_matches_and_rolls_over_midnight() -> None:
    cron = CronSchedule("0 8 * * *")
    assert cron.matches(_dt(h=8, mi=0)) is True
    assert cron.matches(_dt(h=8, mi=1)) is False
    # from 09:00 the next fire is the next day at 08:00 (midnight rollover)
    assert cron.next_after(_dt(h=9)) == _dt(d=2, h=8)


def test_cron_step_field() -> None:
    cron = CronSchedule("*/15 * * * *")
    assert [m for m in range(60) if cron.matches(_dt(mi=m))] == [0, 15, 30, 45]


def test_cron_list_and_range_fields() -> None:
    assert CronSchedule("0,30 * * * *").matches(_dt(mi=30)) is True
    assert CronSchedule("0 9-17 * * *").matches(_dt(h=13)) is True
    assert CronSchedule("0 9-17 * * *").matches(_dt(h=18)) is False


def test_cron_dow_or_dom_semantics() -> None:
    # both dom and dow restricted → OR semantics (standard cron). 2026-01-01 is a Thursday.
    cron = CronSchedule("0 0 1 * 0")  # 1st of month OR Sunday
    assert cron.matches(_dt(d=1)) is True  # the 1st (a Thursday) still matches via dom
    assert cron.matches(_dt(d=4)) is True  # 2026-01-04 is a Sunday → matches via dow
    assert cron.matches(_dt(d=2)) is False  # Friday the 2nd matches neither


def test_cron_alias_and_malformed() -> None:
    assert isinstance(Cron("* * * * *"), CronSchedule)
    with pytest.raises(ValueError, match="5 fields"):
        CronSchedule("0 8 * *")
    with pytest.raises(ValueError, match="out of range"):
        CronSchedule("99 * * * *")


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
