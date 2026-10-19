"""Gate 07: deterministic threshold, real API 5xx, and no-network Telegram tests."""
import asyncio
import io
import json
import logging
import threading
from urllib.parse import parse_qs

from app import alerting
from app.alerting import AlertMonitor, logger


def test_threshold_cooldown_per_operation_and_exact_allowlist():
    ticks = [0.]
    monitor = AlertMonitor(clock=lambda: ticks[0])
    for status in (401, 403, 409, 422, 404, 201):
        assert monitor.record("createOrder", status) is None
    for _ in range(10):
        assert monitor.record("assessChange", 503) is None
        assert monitor.record("createOrder", 499) is None

    assert monitor.record("createOrder", 500) is None
    ticks[0] = 1
    assert monitor.record("createOrder", 502) is None
    ticks[0] = 2
    event = monitor.record("createOrder", 503)
    assert set(event) == {
        "schema", "event", "environment", "operation",
        "failure_count", "window_seconds", "timestamp_utc",
    }
    assert event["schema"] == "handoffguard.alert.v1"
    assert event["event"] == "business_5xx_threshold"
    assert event["environment"] == "demo"
    assert event["operation"] == "createOrder"
    assert event["failure_count"] == 3
    assert event["window_seconds"] == 300
    assert event["timestamp_utc"].endswith("+00:00")

    ticks[0] = 3
    assert monitor.record("createOrder", 500) is None  # cooldown
    ticks[0] = 200
    assert monitor.record("applyApprovedChange", 500) is None
    ticks[0] = 201
    assert monitor.record("applyApprovedChange", 500) is None
    ticks[0] = 202
    assert monitor.record("applyApprovedChange", 500)["operation"] == "applyApprovedChange"

    ticks[0] = 901
    assert monitor.record("createOrder", 500) is None  # previous failures expired
    ticks[0] = 902
    assert monitor.record("createOrder", 500) is None
    ticks[0] = 903
    assert monitor.record("createOrder", 500)["failure_count"] == 3


def test_missing_or_partial_configuration_is_not_a_sent_alert():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        monitor = AlertMonitor(bot_token="123:FAKE-TEST-SECRET", chat_id="")
        for _ in range(3):
            monitor.schedule("createOrder", 500)
        output = stream.getvalue()
        assert "alert_suppressed" in output
        assert "channel_not_configured" in output
        assert "alert_sent" not in output
        assert "FAKE-TEST-SECRET" not in output
    finally:
        logger.removeHandler(handler)


def test_telegram_payload_is_minimal_and_network_is_stubbed(monkeypatch):
    captured = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            assert size == 4096
            return b'{"ok":true,"result":{}}'

    def fake_urlopen(request, timeout):
        captured.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(alerting, "urlopen", fake_urlopen)
    monitor = AlertMonitor(bot_token="123:FAKE-TEST-SECRET", chat_id="111222333")
    event = {
        "schema": "handoffguard.alert.v1",
        "event": "business_5xx_threshold",
        "environment": "demo",
        "operation": "createOrder",
        "failure_count": 3,
        "window_seconds": 300,
        "timestamp_utc": "2026-10-18T00:00:00+00:00",
    }
    monitor._send_telegram(event)
    assert len(captured) == 1
    request, timeout = captured[0]
    assert timeout == 3
    assert request.get_method() == "POST"
    assert request.full_url.startswith("https://api.telegram.org/bot")
    form = parse_qs(request.data.decode())
    assert set(form) == {"chat_id", "text"}
    assert form["chat_id"] == ["111222333"]
    text = form["text"][0]
    assert "createOrder" in text
    assert "3 in 5 minutes" in text
    assert "customer impact is not established" in text
    for private in ("order_id", "actor", "request_id", "token", "FAKE-TEST-SECRET"):
        assert private not in text


def test_transport_failure_never_logs_token_or_exception_details():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        monitor = AlertMonitor(bot_token="123:FAKE-TEST-SECRET", chat_id="111222333")

        def broken_send(_event):
            raise RuntimeError("FAKE-TEST-SECRET PRIVATE-ORDER-TEXT")
        monitor._send_telegram = broken_send
        event = {
            "operation": "createOrder",
            "failure_count": 3,
            "timestamp_utc": "2026-10-18T00:00:00+00:00",
        }
        asyncio.run(monitor._deliver(event))
        output = stream.getvalue()
        assert "alert_delivery_failed" in output
        assert "alert_sent" not in output
        assert "FAKE-TEST-SECRET" not in output
        assert "PRIVATE-ORDER-TEXT" not in output
    finally:
        logger.removeHandler(handler)


def test_real_create_order_503_does_not_change_response_on_notifier_failure(
    client, headers, monkeypatch
):
    """Real FastAPI auth dependency fails closed; disposable SQLite, no orders written."""
    monitor = AlertMonitor(bot_token="123:FAKE-TEST-SECRET", chat_id="111222333")
    seen = []
    delivery_started = threading.Event()

    def broken_send(alert):
        seen.append(alert)
        delivery_started.set()
        raise RuntimeError("FAKE-TEST-SECRET PRIVATE-ORDER-TEXT")

    monitor._send_telegram = broken_send
    client.app.state.alert_monitor = monitor
    monkeypatch.setenv("HANDOFFGUARD_AUTH_TOKENS", "{invalid-json")
    payload = {
        "product_code": "SYNTHETIC-NO-WRITE", "quantity": 100,
        "unit_sales_price_kopeks": 100000,
        "delivery_date": "2026-11-12", "approved_source_id": "synthetic",
    }
    for _ in range(3):
        response = client.post("/api/v1/orders", headers=headers["sales"], json=payload)
        assert response.status_code == 503
        assert response.json() == {"detail": "Authentication server misconfigured"}
        assert "X-Request-ID" in response.headers

    assert delivery_started.wait(2), "The alert task was never scheduled"
    assert len(seen) == 1
    assert seen[0]["operation"] == "createOrder"
    assert set(seen[0]) == {
        "schema", "event", "environment", "operation",
        "failure_count", "window_seconds", "timestamp_utc",
    }
    assert "SYNTHETIC-NO-WRITE" not in json.dumps(seen)
