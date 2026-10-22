"""Read-only local Prometheus backend-availability signal for Gate 08.

NO Docker CLI, shell execution, write operations, credentials or remote endpoints.
An alert is evidence for future human-approved recovery; it is not itself an AI
agent and does not meet on-call remediation criterion #12.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import urlencode
from urllib.request import urlopen

PROMETHEUS_URL = "http://127.0.0.1:9090/api/v1/query"
QUERY = 'up{job="handoffguard_local_business",environment="local_synthetic"}'
EXPECTED_LABELS = {
    "job": "handoffguard_local_business",
    "instance": "backend:8000",
    "environment": "local_synthetic",
}
MAX_REPLY_BYTES = 8192
MAX_SAMPLE_AGE_SECONDS = 30


class State(str, Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Sample:
    state: State
    sampled_at: float | None = None


def parse_prometheus(payload: object, *, now: float) -> Sample:
    """Reject ambiguity, malformed/stale responses, and untrusted targets."""
    unknown = Sample(State.UNKNOWN)
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return unknown
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "vector":
        return unknown
    result = data.get("result")
    if not isinstance(result, list) or len(result) != 1:
        return unknown
    item = result[0]
    if not isinstance(item, dict):
        return unknown
    labels = item.get("metric")
    if not isinstance(labels, dict) or any(
        labels.get(label) != expected for label, expected in EXPECTED_LABELS.items()
    ):
        return unknown
    pair = item.get("value")
    if not isinstance(pair, list) or len(pair) != 2:
        return unknown
    try:
        if isinstance(pair[0], bool) or isinstance(pair[1], bool):
            return unknown
        timestamp = float(pair[0])
        value = float(pair[1])
    except (TypeError, ValueError):
        return unknown
    if not math.isfinite(timestamp) or not math.isfinite(value):
        return unknown
    if timestamp > now + 5 or now - timestamp > MAX_SAMPLE_AGE_SECONDS:
        return unknown
    if value == 1:
        return Sample(State.UP, timestamp)
    if value == 0:
        return Sample(State.DOWN, timestamp)
    return unknown


def fetch_backend_sample(*, now: float | None = None) -> Sample:
    """Query one fixed loopback Prometheus endpoint; fail closed on all errors."""
    when = time.time() if now is None else now
    url = PROMETHEUS_URL + "?" + urlencode({"query": QUERY})
    try:
        with urlopen(url, timeout=3) as response:
            raw = response.read(MAX_REPLY_BYTES + 1)
        if len(raw) > MAX_REPLY_BYTES:
            return Sample(State.UNKNOWN)
        return parse_prometheus(json.loads(raw), now=when)
    except Exception:
        # Do not print remote body, exception, HTTP headers, URLs or credentials.
        return Sample(State.UNKNOWN)


class DownDetector:
    """Emit an incident after two DIFFERENT Prometheus scrape timestamps."""
    def __init__(self):
        self._last_down_timestamp: float | None = None
        self._down_count = 0
        self._alerted = False

    def observe(self, sample: Sample, *, now: float) -> dict | None:
        if sample.state is State.UP:
            self._last_down_timestamp = None
            self._down_count = 0
            self._alerted = False
            return None
        if sample.state is State.UNKNOWN or sample.sampled_at is None:
            # Unknown signal is not a verified outage. Do not re-arm an alert.
            self._last_down_timestamp = None
            self._down_count = 0
            return None
        if self._last_down_timestamp is not None and sample.sampled_at <= self._last_down_timestamp:
            return None
        self._last_down_timestamp = sample.sampled_at
        self._down_count += 1
        if self._down_count < 2 or self._alerted:
            return None
        self._alerted = True
        return {
            "event": "backend_unavailable",
            "environment": "local_synthetic",
            "service": "backend",
            "evidence": "two_distinct_prometheus_scrapes_up_zero",
            "action": "report_only",
            "human_approval_required": True,
            "observed_at_utc": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local lab health detector")
    parser.add_argument("--watch", action="store_true", help="Poll every 5 seconds until Ctrl+C")
    args = parser.parse_args(argv)
    detector = DownDetector()
    try:
        while True:
            now = time.time()
            sample = fetch_backend_sample(now=now)
            print(json.dumps({"event": "backend_sample", "state": sample.state.value}, separators=(",", ":")), flush=True)
            incident = detector.observe(sample, now=now)
            if incident:
                print(json.dumps(incident, separators=(",", ":")), flush=True)
            if not args.watch:
                break
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
