"""Agent coordinator: local read-only outage signal -> optional structured AI advice.

One incident per invocation. No repair tools here. The separate approval-gated
oncall.recovery module NEVER imports or trusts model-generated text.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

from .ai_triage import TriageUnavailable, analyze_incident, extract_advice
from .detector import DownDetector, State, fetch_backend_sample

CONFIRM_LIVE = "SEND ONE SYNTHETIC ALERT TO OPENAI"

# Offline fixture, deliberately not misrepresented as a model inference.
DEMO_ADVICE = {
    "severity": "critical",
    "hypothesis": "unknown",
    "confidence": "low",
    "recommended_action": "inspect_backend_status",
    "explanation_ru": (
        "Prometheus дважды не получил метрики backend. Это подтверждает "
        "недоступность цели сбора, но не устанавливает причину без проверки Docker."
    ),
}


def example_incident() -> dict:
    return {
        "event": "backend_unavailable",
        "environment": "local_synthetic",
        "service": "backend",
        "evidence": "two_distinct_prometheus_scrapes_up_zero",
        "action": "report_only",
        "human_approval_required": True,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local synthetic on-call alert coordinator (no repair tools)"
    )
    parser.add_argument("--demo", action="store_true",
                        help="Show an offline example; no API call or real incident")
    parser.add_argument("--watch", action="store_true",
                        help="Watch local Prometheus until one detected incident")
    parser.add_argument("--live", action="store_true",
                        help="Allow ONE billable OpenAI API analysis, after extra confirmation")
    args = parser.parse_args(argv)

    if args.demo:
        if args.live:
            parser.error("--demo and --live cannot be combined")
        print_json({
            "event": "offline_triage_example", "source": "fixed_fixture_not_ai",
            "incident": example_incident(),
            "advice": DEMO_ADVICE,
            "automatic_repair": False,
        })
        return 0

    if args.live:
        print("An OpenAI API request may incur charges. Only fixed synthetic "
              "incident fields will be sent; no customer records or raw logs.")
        print("No Docker recovery action will be executed.")
        print(f"Type exactly {CONFIRM_LIVE!r} to authorize one request: ", end="", flush=True)
        try:
            approved = input()
        except (EOFError, KeyboardInterrupt):
            approved = ""
        if approved != CONFIRM_LIVE:
            print_json({"event": "ai_analysis_refused", "reason": "explicit_consent_required"})
            return 1

    detector = DownDetector()
    try:
        while True:
            now = time.time()
            sample = fetch_backend_sample(now=now)
            print_json({"event": "backend_sample", "state": sample.state.value})
            incident = detector.observe(sample, now=now)
            if incident:
                print_json(incident)
                if not args.live:
                    print_json({
                        "event": "ai_analysis_skipped",
                        "reason": "api_mode_not_enabled",
                        "automatic_repair": False,
                    })
                    return 0
                try:
                    result = analyze_incident(incident)
                    print_json(result)
                    return 0
                except TriageUnavailable as error:
                    print_json({"event": "ai_analysis_unavailable", "reason": str(error)})
                    return 1
            if not args.watch:
                return 0
            time.sleep(5)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
