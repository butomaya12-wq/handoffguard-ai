"""Issue #22: cloud-only opt-in test, with all Telegram egress mocked."""
import asyncio
import io
import logging
from urllib.parse import parse_qs

from fastapi.testclient import TestClient

from app import alerting
from app.alerting import AlertMonitor, logger
from app.main import create_app


TEST_TOKEN = "123:FAKE-TEST-SECRET"
TEST_CHAT = "111222333"
FLAG = "HANDOFFGUARD_ALERT_DIAGNOSTIC_ON_START"


def test_diagnostic_inert_by_default_and_local_app_even_when_flag_set(
    monkeypatch, tmp_path
):
    sent = []
    monkeypatch.setenv("HANDOFFGUARD_ALERT_TELEGRAM_BOT_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("HANDOFFGUARD_ALERT_TELEGRAM_CHAT_ID", TEST_CHAT)
    monkeypatch.setattr(AlertMonitor, "_send_text", lambda self, msg: sent.append(msg))

    # In cloud_mode, absence of the exact flag must not send a message.
    monkeypatch.delenv(FLAG, raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'disabled.db'}")
    app.state.cloud_mode = True
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert sent == []

    # Ordinary local/Compose backend must never send, even with opt-in.
    monkeypatch.setenv(FLAG, "SEND_ON_NEXT_START")
    local_app = create_app(f"sqlite:///{tmp_path / 'local.db'}")
    with TestClient(local_app) as client:
        assert client.get("/health").status_code == 200
    assert sent == []

    # Near matches of flag value must not send.
    monkeypatch.setenv(FLAG, "send_on_next_start")
    app2 = create_app(f"sqlite:///{tmp_path / 'near-match.db'}")
    app2.state.cloud_mode = True
    with TestClient(app2):
        pass
    assert sent == []


def test_opted_in_cloud_startup_sends_exactly_one_inert_message(
    monkeypatch, tmp_path
):
    sent = []
    monkeypatch.setenv(FLAG, "SEND_ON_NEXT_START")
    monkeypatch.setenv("HANDOFFGUARD_ALERT_TELEGRAM_BOT_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("HANDOFFGUARD_ALERT_TELEGRAM_CHAT_ID", TEST_CHAT)
    monkeypatch.setattr(AlertMonitor, "_send_text", lambda self, msg: sent.append(msg))

    app = create_app(f"sqlite:///{tmp_path / 'enabled.db'}")
    app.state.cloud_mode = True
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
    assert len(sent) == 1
    message = sent[0]
    assert "DIAGNOSTIC TEST" in message
    assert "Not a real incident" in message
    assert "No HTTP 5xx" in message
    assert "No orders modified" in message
    assert "FAKE-TEST-SECRET" not in message
    assert TEST_CHAT not in message
    assert "order_id" not in message


def test_actual_telegram_diagnostic_transport_has_only_safe_payload(monkeypatch):
    captured = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            assert size == 4096
            return b'{"ok":true,"result":{}}'

    def fake_urlopen(request, timeout):
        captured.append((request, timeout))
        return Response()

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        monkeypatch.setattr(alerting, "urlopen", fake_urlopen)
        monitor = AlertMonitor(bot_token=TEST_TOKEN, chat_id=TEST_CHAT)
        assert asyncio.run(monitor.send_diagnostic()) is True
    finally:
        logger.removeHandler(handler)

    assert len(captured) == 1
    request, timeout = captured[0]
    assert timeout == 3
    assert request.get_method() == "POST"
    form = parse_qs(request.data.decode())
    assert set(form) == {"chat_id", "text"}
    assert form["chat_id"] == [TEST_CHAT]
    msg = form["text"][0]
    assert "DIAGNOSTIC TEST" in msg
    assert "Not a real incident" in msg
    for secret in (TEST_TOKEN, TEST_CHAT, "order_id", "request_id", "actor"):
        assert secret not in msg
        assert secret not in stream.getvalue()
    assert '"event":"diagnostic_sent"' in stream.getvalue()
    assert '"operation":"diagnostic"' in stream.getvalue()
    assert "alert_sent" not in stream.getvalue()


def test_missing_bot_config_is_suppressed_but_cloud_starts(monkeypatch, tmp_path):
    monkeypatch.setenv(FLAG, "SEND_ON_NEXT_START")
    monkeypatch.delenv("HANDOFFGUARD_ALERT_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("HANDOFFGUARD_ALERT_TELEGRAM_CHAT_ID", raising=False)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        app = create_app(f"sqlite:///{tmp_path / 'no-credentials.db'}")
        app.state.cloud_mode = True
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
    finally:
        logger.removeHandler(handler)
    assert '"event":"diagnostic_suppressed"' in stream.getvalue()
    assert '"reason":"channel_not_configured"' in stream.getvalue()
    assert '"event":"diagnostic_sent"' not in stream.getvalue()


def test_failed_transport_does_not_break_cloud_or_expose_secrets(
    monkeypatch, tmp_path
):
    monkeypatch.setenv(FLAG, "SEND_ON_NEXT_START")
    monkeypatch.setenv("HANDOFFGUARD_ALERT_TELEGRAM_BOT_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("HANDOFFGUARD_ALERT_TELEGRAM_CHAT_ID", TEST_CHAT)

    def fail(self, message):
        raise RuntimeError("FAKE-TEST-SECRET PRIVATE-ORDER-DATA")
    monkeypatch.setattr(AlertMonitor, "_send_text", fail)

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        app = create_app(f"sqlite:///{tmp_path / 'transport-failure.db'}")
        app.state.cloud_mode = True
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
    finally:
        logger.removeHandler(handler)
    assert '"event":"diagnostic_delivery_failed"' in stream.getvalue()
    assert "FAKE-TEST-SECRET" not in stream.getvalue()
    assert "PRIVATE-ORDER-DATA" not in stream.getvalue()
    assert '"event":"diagnostic_sent"' not in stream.getvalue()
