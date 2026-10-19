"""Best-effort, in-process alerting for the HandoffGuard educational demo.

No external monitoring, durable counters, customer details or new credentials.
Only createOrder/applyApprovedChange HTTP 5xx are counted. Never use as a pager.
"""
import asyncio
import json
import logging
import os
import re
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ALERT_OPERATIONS = frozenset({"createOrder", "applyApprovedChange"})
WINDOW_SECONDS = 300
THRESHOLD = 3
COOLDOWN_SECONDS = 900

logger = logging.getLogger("handoffguard.alerting")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def _diagnostic(event: str, operation: str, reason: str | None = None) -> None:
    """Only fixed machine-owned strings reach the log."""
    record = {
        "schema": "handoffguard.alerting.v1",
        "event": event,
        "environment": "demo",
        "operation": operation,
    }
    if reason is not None:
        record["reason"] = reason
    logger.info(json.dumps(record, separators=(",", ":")))


class AlertMonitor:
    """Per-app, per-process rolling 5xx threshold; resets on restart/sleep."""

    def __init__(self, *, bot_token: str = "", chat_id: str = "", clock=monotonic):
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._clock = clock
        self._hits = defaultdict(deque)
        self._last_alert = {}
        self._pending = set()
        # Private Telegram chat IDs are numeric. Reject partial/malformed config.
        self._configured = bool(
            re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", bot_token)
            and re.fullmatch(r"-?[0-9]+", chat_id)
        )

    @classmethod
    def from_environment(cls):
        return cls(
            bot_token=os.getenv("HANDOFFGUARD_ALERT_TELEGRAM_BOT_TOKEN", ""),
            chat_id=os.getenv("HANDOFFGUARD_ALERT_TELEGRAM_CHAT_ID", ""),
        )

    def record(self, operation: str, status: int) -> dict | None:
        """Pure local bookkeeping. Returns only allowlisted fields at threshold."""
        if operation not in ALERT_OPERATIONS or not 500 <= status <= 599:
            return None

        now = self._clock()
        hits = self._hits[operation]
        while hits and now - hits[0] > WINDOW_SECONDS:
            hits.popleft()
        hits.append(now)

        if len(hits) < THRESHOLD:
            return None
        last = self._last_alert.get(operation)
        if last is not None and now - last < COOLDOWN_SECONDS:
            return None

        self._last_alert[operation] = now
        return {
            "schema": "handoffguard.alert.v1",
            "event": "business_5xx_threshold",
            "environment": "demo",
            "operation": operation,
            "failure_count": len(hits),
            "window_seconds": WINDOW_SECONDS,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }

    def schedule(self, operation: str, status: int) -> None:
        """Schedule delivery outside the request; never await Telegram on an API call."""
        alert = self.record(operation, status)
        if alert is None:
            return
        if not self._configured:
            _diagnostic("alert_suppressed", operation, "channel_not_configured")
            return
        try:
            task = asyncio.create_task(self._deliver(alert))
            self._pending.add(task)
            task.add_done_callback(self._pending.discard)
        except Exception:
            _diagnostic("alert_suppressed", operation, "scheduler_unavailable")

    async def _deliver(self, alert: dict) -> None:
        try:
            await asyncio.to_thread(self._send_telegram, alert)
        except Exception:
            # NEVER log the exception: transport exceptions may contain the bot token URL.
            _diagnostic("alert_delivery_failed", alert["operation"])
        else:
            _diagnostic("alert_sent", alert["operation"])

    async def send_diagnostic(self) -> bool:
        """Opt-in backend egress proof; never create artificial errors or touch orders.

        Called only on explicitly enabled cloud startup. One attempt per
        process start, NOT durable exactly-once across Render restarts.
        """
        if not self._configured:
            _diagnostic("diagnostic_suppressed", "diagnostic", "channel_not_configured")
            return False
        message = (
            "HandoffGuard AI | DIAGNOSTIC TEST\n"
            "Backend-to-Telegram delivery test.\n"
            "No HTTP 5xx triggered. No orders modified.\n"
            "Not a real incident."
        )
        try:
            await asyncio.to_thread(self._send_text, message)
        except Exception:
            # Transport exceptions may embed the Bot API token URL.
            _diagnostic("diagnostic_delivery_failed", "diagnostic")
            return False
        _diagnostic("diagnostic_sent", "diagnostic")
        return True

    def _send_telegram(self, alert: dict) -> None:
        """HTTPS Bot API request with a short timeout; no token in logs."""
        message = (
            "HandoffGuard AI | DEMO ALERT\n"
            "Repeated HTTP 5xx on a business operation\n"
            f"Operation: {alert['operation']}\n"
            f"Failures: {alert['failure_count']} in 5 minutes\n"
            f"UTC: {alert['timestamp_utc']}\n"
            "Signal only; customer impact is not established."
        )
        self._send_text(message)

    def _send_text(self, message: str) -> None:
        """Shared HTTPS transport for real alerts and the inert diagnostic."""
        data = urlencode({"chat_id": self._chat_id, "text": message}).encode("utf-8")
        request = Request(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            # Telegram may return HTTP 200 with ok:false; never log its raw response.
            body = json.loads(response.read(4096))
            if not isinstance(body, dict) or body.get("ok") is not True:
                raise RuntimeError("Telegram delivery not confirmed")
