"""On-call coordinator for one isolated synthetic local lab incident.

Optional session-preauthorized recovery starts only the fixed lab backend after
a verified outage and a real model recommendation. Model text is never a shell
command or a Docker argument; all recovery eligibility checks are deterministic.
No cloud services, customer data, or recurring unattended scheduling.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

from . import recovery
from .ai_triage import (
    MODEL, TriageUnavailable, analyze_incident, validate_advice,
)
from .detector import DownDetector, State, fetch_backend_sample

CONFIRM_LIVE = "SEND ONE SYNTHETIC ALERT TO OPENAI"
CONFIRM_AUTO = "AUTHORIZE ONE LOCAL BACKEND START"

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


def auto_recover(incident: dict, report: dict) -> dict:
    """Treat AI advice as a veto only; independent local safety checks decide.

    A permitted action is one fixed Docker Compose START of one stopped backend,
    never a model-chosen command. Session authorization is obtained before watch.
    """
    if (
        incident.get("event") != "backend_unavailable"
        or incident.get("environment") != "local_synthetic"
        or incident.get("service") != "backend"
        or incident.get("evidence") != "two_distinct_prometheus_scrapes_up_zero"
        or incident.get("action") != "report_only"
        or incident.get("human_approval_required") is not True
        or report.get("event") != "ai_incident_advice"
        or report.get("source") != "openai_api"
        or report.get("model") != MODEL
        or report.get("human_approval_required") is not True
    ):
        return {"event": "auto_recovery_refused", "reason": "unverified_ai_or_incident"}
    try:
        advice = validate_advice(report.get("advice"))
    except TriageUnavailable:
        return {"event": "auto_recovery_refused", "reason": "invalid_ai_advice"}
    if advice["recommended_action"] != "request_human_approved_local_backend_start":
        return {"event": "auto_recovery_skipped", "reason": "model_did_not_recommend_start"}
    try:
        recovery.check_local_docker()
        result = recovery.perform(approved=True)
    except recovery.UnsafeRecovery as error:
        return {"event": "auto_recovery_refused", "reason": str(error)}
    if result.get("event") == "backend_recovered":
        result["authorization"] = "explicit_session_preapproval"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="One-shot local lab triage and optional bounded preapproved recovery"
    )
    parser.add_argument("--demo", action="store_true",
                        help="Show an offline example; no API call or real incident")
    parser.add_argument("--watch", action="store_true",
                        help="Watch local Prometheus until one detected incident")
    parser.add_argument("--live", action="store_true",
                        help="Allow ONE billable OpenAI API analysis, after extra confirmation")
    parser.add_argument("--auto-recover", action="store_true",
                        help="PREAUTHORIZE one allowlisted local backend start, gated by AI advice and independent checks")
    args = parser.parse_args(argv)

    if args.auto_recover and (not args.live or not args.watch or args.demo):
        parser.error("--auto-recover requires --watch --live and cannot use --demo")

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

    if args.auto_recover:
        # Abort before any paid request or outage if the local lab is not ready.
        if not os.environ.get("OPENAI_API_KEY"):
            print_json({"event": "auto_recovery_refused", "reason": "api_key_not_configured"})
            return 1
        try:
            recovery.check_local_docker()
            state, health = recovery.container_state()
        except recovery.UnsafeRecovery as error:
            print_json({"event": "auto_recovery_refused", "reason": str(error)})
            return 1
        if state != "running" or health != "healthy":
            print_json({"event": "auto_recovery_refused", "reason": "backend_not_initially_healthy"})
            return 1

    if args.live:
        print("An OpenAI API request may incur charges. Only fixed synthetic "
              "incident fields will be sent; no customer records or raw logs.")
        if args.auto_recover:
            print("If AI recommends a start and independent checks pass, ONE fixed "
                  "local lab backend start may run without additional input. "
                  "No Docker commands or arguments come from AI.")
        else:
            print("No Docker recovery action will be executed.")
        print(f"Type exactly {CONFIRM_LIVE!r} to authorize one request: ", end="", flush=True)
        try:
            approved = input()
        except (EOFError, KeyboardInterrupt):
            approved = ""
        if approved != CONFIRM_LIVE:
            print_json({"event": "ai_analysis_refused", "reason": "explicit_consent_required"})
            return 1
        if args.auto_recover:
            print("AUTHORIZE ONE preapproved local synthetic backend START only. "
                  "No stop/restart, no cloud, no other service, no customer edits.")
            print(f"Type exactly {CONFIRM_AUTO!r} to preauthorize once: ",
                  end="", flush=True)
            try:
                approved = input()
            except (EOFError, KeyboardInterrupt):
                approved = ""
            if approved != CONFIRM_AUTO:
                print_json({"event": "auto_recovery_refused", "reason": "explicit_preapproval_required"})
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
                    if args.auto_recover:
                        recovered = auto_recover(incident, result)
                        print_json(recovered)
                        return 0 if recovered.get("event") == "backend_recovered" else 1
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
