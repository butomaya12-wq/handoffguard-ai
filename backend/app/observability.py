"""Allowlisted, log-derived observability for the educational business workflow.

Never log raw URLs, path parameters, actor IDs, request/response bodies, headers,
credentials, exception messages, DB configuration or customer-provided text.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.routing import APIRoute

TRACE_HEADER = "X-Workflow-Trace"
REQUEST_HEADER = "X-Request-ID"
EVENT = "business_operation_completed"
TRACKED_OPERATIONS = frozenset({
    "createOrder", "recordProductionReview", "createChange", "assessChange",
    "submitForApproval", "decideChange", "recordCustomerAcceptance",
    "applyApprovedChange",
})

logger = logging.getLogger("handoffguard.observability")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def _safe_trace(raw: str | None) -> str:
    """Only canonical UUID4 is accepted; arbitrary user text is never emitted."""
    if raw and len(raw) == 36:
        try:
            parsed = UUID(raw)
            if parsed.version == 4 and str(parsed) == raw:
                return raw
        except ValueError:
            pass
    return str(uuid4())


def _result(status: int) -> str:
    if 200 <= status < 400:
        return "success"
    if status in {401, 403, 409, 422}:
        return "blocked"
    if status >= 500:
        return "failure"
    return "client_error"


async def observe_business_operation(request: Request, call_next):
    """One event per tracked HTTP operation, including denied or failed calls."""
    start = perf_counter()
    workflow_trace_id = _safe_trace(request.headers.get(TRACE_HEADER))
    request_id = str(uuid4())
    status = 500
    response = None
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        operation = route.operation_id if isinstance(route, APIRoute) else None
        if request.method == "POST" and operation in TRACKED_OPERATIONS:
            elapsed_ms = round(max(0.0, (perf_counter() - start) * 1000), 3)
            event = {
                "schema": "handoffguard.observability.v1",
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "event": EVENT,
                "workflow_trace_id": workflow_trace_id,
                "request_id": request_id,
                "operation": operation,
                "outcome": _result(status),
                "http_status": status,
                "duration_ms": elapsed_ms,
                "metric_name": "business_operation_total",
                "metric_value": 1,
            }
            logger.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
            if response is not None:
                response.headers[REQUEST_HEADER] = request_id
