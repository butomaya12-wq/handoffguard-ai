"""Gate 07: opt-in live transport diagnostic; no fake incidents or DB writes."""
import asyncio
import io
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app import alerting
from app.alerting import AlertMonitor, logger
from app.main import create_app


NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
BOT_TOKEN = "123:FAKE-TEST-SECRET"
CHAT_ID = "111222333"


def expiry(seconds: int) -> str:
    return (NOW + timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def configured_monitor() -> AlertMonitor:
    return AlertMonitor(bot_token=BOT_TOKEN, chat_id=CHAT_ID)


def test_opt_in_requires_strict_near_future_utc_and_expired_values_do_nothing():
    invalid = [
        "", "true", "now", "2026-10-19T12:05:00+00:00",
        "2026-10-19T12:04:00", "2026-13-19T12:01:00Z",
        expiry(-1), expiry(0), expiry(301), "x" * 10000,
    ]
    for value in invalid:
        monitor = configured_monitor()
        assert monitor.schedule_startup_test(value, now=NOW) is False
        assert monitor._startup_test_attempted is False
        assert not monitor._pending
    assert configured_monitor().schedule_startup_test(expiry(60), now=NOW.replace(tzinfo=None)) is False


def test_opt_in_one_attempt_only_reuses_transport_without_touching_5xx_counters():
    sent = []

    async def run():
        monitor = configured_monitor()
        monitor._post_telegram_text = sent.append
        assert monitor.schedule_startup_test(expiry(120), now=NOW) is True
        assert monitor.schedule_startup_test(expiry(120), now=NOW) is False
        await asyncio.gather(*tuple(monitor._pending))
        assert monitor.record("createOrder", 500) is None
        assert monitor.record("applyApprovedChange", 500) is None
        assert monitor._last_alert == {}
        assert len(sent) == 1
        message = sent[0]
        assert "TEST - NOT AN INCIDENT" in message
        assert "No HTTP errors were generated" in message
        assert "UTC: 2026-10-19T12:00:00+00:00" in message
        for private in ("order_id", "customer", "Bearer ", BOT_TOKEN, CHAT_ID):
            assert private not in message

    asyncio.run(run())


def test_test_delivery_uses_same_bot_api_endpoint_and_safe_fields(monkeypatch):
    observed = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, max_size):
            assert max_size == 4096
            return b'{"ok":true,"result":{}}'

    def fake_urlopen(request, timeout):
        observed.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(alerting, "urlopen", fake_urlopen)
    monitor = configured_monitor()
    monitor._post_telegram_text("HandoffGuard AI | TEST - NOT AN INCIDENT")
    assert len(observed) == 1
    request, timeout = observed[0]
    assert timeout == 3
    assert request.get_method() == "POST"
    assert request.full_url.endswith("/sendMessage")
    data = parse_qs(request.data.decode())
    assert set(data) == {"chat_id", "text"}
    assert data["chat_id"] == [CHAT_ID]
    assert data["text"] == ["HandoffGuard AI | TEST - NOT AN INCIDENT"]


def test_delivery_failure_redacts_secrets_and_never_blocks_startup():
    logs = io.StringIO()
    handler = logging.StreamHandler(logs)
    logger.addHandler(handler)
    try:
        monitor = configured_monitor()

        def failed(_):
            raise RuntimeError(BOT_TOKEN + " CUSTOMER-PRIVATE")

        monitor._post_telegram_text = failed

        async def run():
            assert monitor.schedule_startup_test(expiry(60), now=NOW)
            await asyncio.gather(*tuple(monitor._pending))

        asyncio.run(run())
        output = logs.getvalue()
        assert "alert_test_failed" in output
        assert "alert_test_sent" not in output
        assert BOT_TOKEN not in output
        assert "CUSTOMER-PRIVATE" not in output
        assert "alert_sent" not in output
    finally:
        logger.removeHandler(handler)


def test_missing_bot_config_suppresses_delivery_even_with_valid_window():
    logs = io.StringIO()
    handler = logging.StreamHandler(logs)
    logger.addHandler(handler)
    try:
        monitor = AlertMonitor(bot_token=BOT_TOKEN, chat_id="")
        assert monitor.schedule_startup_test(expiry(60), now=NOW) is False
        assert "channel_not_configured" in logs.getvalue()
        assert "alert_test_suppressed" in logs.getvalue()
        assert "alert_test_sent" not in logs.getvalue()
        assert BOT_TOKEN not in logs.getvalue()
    finally:
        logger.removeHandler(handler)


def test_fastapi_lifespan_schedules_test_only_and_preserves_empty_order_data(
    tmp_path, monkeypatch
):
    delivered = threading.Event()
    messages = []

    def fake_post(_self, message):
        messages.append(message)
        delivered.set()

    monkeypatch.setattr(AlertMonitor, "_post_telegram_text", fake_post)
    monkeypatch.setenv("HANDOFFGUARD_ALERT_TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HANDOFFGUARD_ALERT_TELEGRAM_CHAT_ID", CHAT_ID)
    monkeypatch.setenv(
        "HANDOFFGUARD_ALERT_TEST_UNTIL_UTC",
        (datetime.now(timezone.utc) + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    db_path = tmp_path / "startup-test.db"
    with TestClient(create_app(f"sqlite:///{db_path}")) as client:
        assert client.get("/health").status_code == 200
        assert delivered.wait(timeout=3), "Startup diagnostic never ran"
    assert len(messages) == 1
    assert "TEST - NOT AN INCIDENT" in messages[0]

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            for table in ("orders", "order_revisions", "changes",
                          "approval_decisions", "customer_acceptances"):
                assert conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    finally:
        engine.dispose()
