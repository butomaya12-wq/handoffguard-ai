"""Real synthetic V1→V2 telemetry, correlation and redaction tests (#16)."""
import json
import re
from uuid import UUID, uuid4


PREFIX = '{"schema":"handoffguard.observability.v1"'


def emitted_events(caplog):
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "handoffguard.observability"
        and record.getMessage().startswith(PREFIX)
    ]


def test_synthetic_v1_to_v2_has_correlated_safe_events(client, headers, caplog):
    trace = str(uuid4())

    def auth(role):
        return {**headers[role], "X-Workflow-Trace": trace}

    created = client.post("/api/v1/orders", headers=auth("sales"), json={
        "product_code": "SAFE-SYNTHETIC",
        "quantity": 100,
        "unit_sales_price_kopeks": 100000,
        "delivery_date": "2026-11-12",
        "approved_source_id": "synthetic-only",
    })
    assert created.status_code == 201
    order_id = created.json()["id"]

    review = client.post(f"/api/v1/orders/{order_id}/production-reviews",
        headers=auth("production"), json={
            "production_status": "NOT_STARTED",
            "completed_quantity": 0,
            "feasibility": "CONFIRMED",
            "note": "PRIVATE-PRODUCTION-TEXT-DO-NOT-LOG",
        })
    assert review.status_code == 201

    change = client.post(f"/api/v1/orders/{order_id}/changes", headers=auth("sales"), json={
        "reason": "PRIVATE-REQUEST-TEXT-DO-NOT-LOG",
        "requested_quantity": 120,
    })
    assert change.status_code == 201
    change_id = change.json()["id"]

    assessment = client.post(f"/api/v1/changes/{change_id}/assess", headers=auth("sales"))
    assert assessment.status_code == 200
    fingerprint = assessment.json()["fingerprint"]
    assert assessment.json()["readiness"] == "READY_FOR_APPROVAL"

    submit = client.post(f"/api/v1/changes/{change_id}/submit", headers=auth("sales"))
    assert submit.status_code == 200

    denied = client.post(f"/api/v1/changes/{change_id}/decision", headers=auth("sales"),
        json={"action": "APPROVE", "assessment_fingerprint": fingerprint, "note": "unauthorized"})
    assert denied.status_code == 403

    approved = client.post(f"/api/v1/changes/{change_id}/decision", headers=auth("approver"),
        json={"action": "APPROVE", "assessment_fingerprint": fingerprint,
              "note": "Synthetic approval"})
    assert approved.status_code == 200

    premature = client.post(f"/api/v1/changes/{change_id}/apply", headers=auth("approver"))
    assert premature.status_code == 409

    acceptance = client.post(f"/api/v1/changes/{change_id}/customer-acceptance",
        headers=auth("sales"), json={
            "quantity": 120, "unit_sales_price_kopeks": 100000,
            "delivery_date": "2026-11-12",
            "source_name": "synthetic-only",
            "evidence_text": "PRIVATE-ACCEPTANCE-TEXT-DO-NOT-LOG",
        })
    assert acceptance.status_code == 201

    applied = client.post(f"/api/v1/changes/{change_id}/apply", headers=auth("approver"))
    assert applied.status_code == 201
    assert applied.json()["approved_revision"] == 2
    history = client.get(f"/api/v1/orders/{order_id}/revisions", headers=auth("sales"))
    assert [row["quantity"] for row in history.json()] == [100, 120]

    events = emitted_events(caplog)
    assert len(events) == 10
    assert {ev["workflow_trace_id"] for ev in events} == {trace}
    assert len({ev["request_id"] for ev in events}) == len(events)
    assert [ev["operation"] for ev in events] == [
        "createOrder", "recordProductionReview", "createChange",
        "assessChange", "submitForApproval", "decideChange", "decideChange",
        "applyApprovedChange", "recordCustomerAcceptance", "applyApprovedChange",
    ]
    assert [ev["http_status"] for ev in events] == [
        201, 201, 201, 200, 200, 403, 200, 409, 201, 201,
    ]
    assert [ev["outcome"] for ev in events].count("blocked") == 2
    for ev in events:
        assert UUID(ev["request_id"]).version == 4
        assert ev["event"] == "business_operation_completed"
        assert ev["duration_ms"] >= 0
        assert ev["metric_name"] == "business_operation_total"
        assert ev["metric_value"] == 1
        assert ev["timestamp_utc"].endswith("+00:00")
        assert set(ev) == {
            "schema", "timestamp_utc", "event", "workflow_trace_id",
            "request_id", "operation", "outcome", "http_status",
            "duration_ms", "metric_name", "metric_value",
        }
    assert UUID(created.headers["X-Request-ID"]).version == 4
    assert created.headers["X-Request-ID"] == events[0]["request_id"]
    raw = json.dumps(events)
    for private in [
        "PRIVATE-PRODUCTION-TEXT", "PRIVATE-REQUEST-TEXT", "PRIVATE-ACCEPTANCE-TEXT",
        order_id, change_id, fingerprint, "test-sales-token",
    ]:
        assert private not in raw


def test_invalid_trace_and_secret_are_never_logged(client, headers, caplog):
    secret = "PRIVATE-MALICIOUS-TRACE-DO-NOT-LOG"
    response = client.post("/api/v1/orders",
        headers={**headers["sales"], "X-Workflow-Trace": secret},
        json={"product_code": "SYNTHETIC", "quantity": 100,
              "unit_sales_price_kopeks": 100000, "delivery_date": "2026-11-12",
              "approved_source_id": "synthetic-only"})
    assert response.status_code == 201
    events = emitted_events(caplog)
    assert len(events) == 1
    assert UUID(events[0]["workflow_trace_id"]).version == 4
    assert secret not in json.dumps(events)
    assert re.fullmatch(r"[0-9a-f-]{36}", response.headers["X-Request-ID"])
