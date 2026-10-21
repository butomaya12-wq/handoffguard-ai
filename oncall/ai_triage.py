"""Optional AI triage of an allowlisted *synthetic* local outage.

NO general tools, Docker access, customer payloads, log contents or secret output.
Default mode makes NO API call. Paid API usage requires a deliberate --live flag
on the separate agent runner and an API key obtained outside this repository.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.request import Request, urlopen

API_ENDPOINT = "https://api.openai.com/v1/responses"
MODEL = "gpt-5.4-mini"
ALLOWED_EVENT = "backend_unavailable"
ALLOWED_EVIDENCE = "two_distinct_prometheus_scrapes_up_zero"

RESULT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "severity": {"type": "string", "enum": ["warning", "critical"]},
        "hypothesis": {"type": "string", "enum": ["stopped_backend", "scrape_or_network_issue", "unknown"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "recommended_action": {"type": "string", "enum": [
            "inspect_backend_status",
            "request_human_approved_local_backend_start",
            "investigate_manually",
        ]},
        "explanation_ru": {"type": "string"},
    },
    "required": ["severity", "hypothesis", "confidence", "recommended_action", "explanation_ru"],
}

SYSTEM_INSTRUCTIONS = (
    "You are a read-only incident analyst for one isolated, synthetic local Docker lab. "
    "You receive a sanitized, machine-generated Prometheus incident: two distinct 'up=0' scrapes. "
    "Never assume that Prometheus alone proves a container is stopped. "
    "Distinguish observed lack of scrape availability from suspected causes. "
    "No access to Docker, tools, customer records, terminal commands or cloud systems. "
    "Only suggest human-gated checks or actions. Explain briefly in Russian. "
    "Never claim you fixed anything. Output JSON matching the supplied schema."
)


class TriageUnavailable(RuntimeError):
    """No diagnostic output or raw exception string may leak API secrets."""


def sanitize_incident(event: object) -> dict:
    """Fail closed; never forward arbitrary user, customer or log text to AI."""
    if not isinstance(event, dict):
        raise TriageUnavailable("invalid_incident")
    if (
        event.get("event") != ALLOWED_EVENT
        or event.get("environment") != "local_synthetic"
        or event.get("service") != "backend"
        or event.get("evidence") != ALLOWED_EVIDENCE
        or event.get("action") != "report_only"
        or event.get("human_approval_required") is not True
    ):
        raise TriageUnavailable("invalid_incident")
    timestamp = event.get("observed_at_utc")
    if not isinstance(timestamp, str) or len(timestamp) > 40:
        raise TriageUnavailable("invalid_timestamp")
    try:
        value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        raise TriageUnavailable("invalid_timestamp") from None
    if value.tzinfo is None or value.utcoffset() is None:
        raise TriageUnavailable("invalid_timestamp")
    # Deliberately do not include the timestamp or any provided extra keys:
    # only four fixed machine-owned values reach the model.
    return {
        "environment": "local_synthetic",
        "service": "backend",
        "signal": "two_distinct_prometheus_scrapes_up_zero",
        "human_approval_required": True,
    }


def validate_advice(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != set(RESULT_SCHEMA["required"]):
        raise TriageUnavailable("invalid_model_output")
    for name in ("severity", "hypothesis", "confidence", "recommended_action"):
        if value[name] not in RESULT_SCHEMA["properties"][name]["enum"]:
            raise TriageUnavailable("invalid_model_output")
    explanation = value.get("explanation_ru")
    if (
        not isinstance(explanation, str)
        or not 1 <= len(explanation) <= 240
        or any(ord(char) < 32 and char not in "\n\t" for char in explanation)
    ):
        raise TriageUnavailable("invalid_model_output")
    # No model-proposed action is executable: it is display-only advice.
    return dict(value)


def request_payload(event: dict) -> dict:
    sanitized = sanitize_incident(event)
    return {
        "model": MODEL,
        "store": False,
        "tools": [],
        "max_output_tokens": 600,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": "Analyze this machine-generated local diagnostic event: " +
                 json.dumps(sanitized, separators=(",", ":")),
        "text": {"format": {
            "type": "json_schema",
            "name": "handoffguard_incident_analysis",
            "strict": True,
            "schema": RESULT_SCHEMA,
        }},
    }


def extract_advice(response: object) -> dict:
    if not isinstance(response, dict) or response.get("status") != "completed":
        raise TriageUnavailable("model_response_incomplete")
    messages = response.get("output")
    if not isinstance(messages, list):
        raise TriageUnavailable("model_response_invalid")
    texts = []
    for item in messages:
        if isinstance(item, dict) and item.get("type") == "message":
            content = item.get("content")
            if not isinstance(content, list):
                raise TriageUnavailable("model_response_invalid")
            for part in content:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    texts.append(part.get("text"))
                elif isinstance(part, dict) and part.get("type") == "refusal":
                    raise TriageUnavailable("model_refusal")
    if len(texts) != 1 or not isinstance(texts[0], str):
        raise TriageUnavailable("model_response_invalid")
    try:
        parsed = json.loads(texts[0])
    except (ValueError, TypeError):
        raise TriageUnavailable("model_response_invalid") from None
    return validate_advice(parsed)


def analyze_incident(event: dict, *, token: str | None = None, transport=None) -> dict:
    """Exactly one optional external request. Never exposed through default CLI."""
    secret = token if token is not None else os.environ.get("OPENAI_API_KEY", "")
    if not isinstance(secret, str) or not secret.strip():
        raise TriageUnavailable("api_key_not_configured")
    payload = request_payload(event)  # fully validate before network
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(API_ENDPOINT, data=body, method="POST", headers={
        "Authorization": "Bearer " + secret,
        "Content-Type": "application/json",
    })
    sender = transport if transport is not None else urlopen
    try:
        with sender(request, timeout=20) as result:
            data = result.read(16_385)
        if len(data) > 16_384:
            raise TriageUnavailable("model_response_too_large")
        answer = extract_advice(json.loads(data))
    except TriageUnavailable:
        raise
    except Exception:
        # HTTP transport errors sometimes contain raw URLs or credentials.
        raise TriageUnavailable("model_request_failed") from None
    return {
        "event": "ai_incident_advice",
        "source": "openai_api",
        "model": MODEL,
        "advice": answer,
        "automatic_repair": False,
        "human_approval_required": True,
    }
