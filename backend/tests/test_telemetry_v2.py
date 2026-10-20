"""Isolated local telemetry v2: real span, bounded metrics and fail-open paths."""
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.observability import logger
from app.telemetry_v2 import TelemetryV2

SYNTHETIC_TOKEN = "synthetic-lab-sales-only"
SYNTHETIC_PAYLOAD = {
    "product_code": "SAFE-SYNTHETIC-OBS",
    "quantity": 100,
    "unit_sales_price_kopeks": 100000,
    "delivery_date": "2026-11-12",
    "approved_source_id": "synthetic-only",
}


def test_default_local_route_not_exposed(client):
    """The existing default app must never publish unauthenticated metrics."""
    response = client.get("/internal/metrics")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not found"}


def test_v2_rejects_enabled_cloud_and_nonlocal_exporter(monkeypatch):
    monkeypatch.setenv("HANDOFFGUARD_OBSERVABILITY_V2_ENABLED", "1")
    monkeypatch.setenv("HANDOFFGUARD_OTLP_TRACES_ENDPOINT", "https://example.org/v1/traces")
    with pytest.raises(RuntimeError, match="isolated Jaeger collector"):
        TelemetryV2.from_environment()
    monkeypatch.setenv("HANDOFFGUARD_OTLP_TRACES_ENDPOINT", "http://jaeger:4318/v1/traces")
    with pytest.raises(RuntimeError, match="cannot be enabled in the cloud"):
        TelemetryV2.from_environment(cloud_mode=True)


def test_real_opentelemetry_spans_and_cumulative_metrics_no_secret(monkeypatch, tmp_path, caplog):
    pytest.importorskip("opentelemetry.sdk.trace")
    pytest.importorskip("prometheus_client")
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    monkeypatch.setattr(TelemetryV2, "_make_exporter", staticmethod(lambda endpoint: exporter))
    monkeypatch.setenv("HANDOFFGUARD_OBSERVABILITY_V2_ENABLED", "1")
    monkeypatch.setenv("HANDOFFGUARD_OTLP_TRACES_ENDPOINT", "http://jaeger:4318/v1/traces")
    monkeypatch.setenv("HANDOFFGUARD_AUTH_TOKENS", json.dumps({
        SYNTHETIC_TOKEN: {"id": "synthetic-local", "role": "sales"},
    }))
    logger.addHandler(caplog.handler)
    trace = str(uuid4())
    try:
        with TestClient(create_app(f"sqlite:///{tmp_path / 'synthetic-telemetry.db'}")) as api:
            headers = {
                "Authorization": "Bearer " + SYNTHETIC_TOKEN,
                "X-Workflow-Trace": trace,
            }
            response = api.post("/api/v1/orders", headers=headers, json=SYNTHETIC_PAYLOAD)
            assert response.status_code == 201, response.text
            denied = api.post("/api/v1/orders", json=SYNTHETIC_PAYLOAD)
            assert denied.status_code == 401
            exported = api.get("/internal/metrics")
            assert exported.status_code == 200
            assert "Cache-Control" in exported.headers
            body = exported.text
            assert 'handoffguard_business_operations_total{operation="createOrder",outcome="success",status_class="2xx"} 1.0' in body
            assert 'handoffguard_business_operations_total{operation="createOrder",outcome="blocked",status_class="4xx"} 1.0' in body
            assert "handoffguard_business_operation_duration_seconds_bucket" in body
            assert SYNTHETIC_TOKEN not in body
            assert SYNTHETIC_PAYLOAD["product_code"] not in body
            assert "synthetic-local" not in body
            assert api.app.state.telemetry_v2._provider.force_flush(timeout_millis=2000)
            spans = exporter.get_finished_spans()
            assert len(spans) == 2
            assert {span.name for span in spans} == {"createOrder"}
            assert {span.attributes["handoffguard.outcome"] for span in spans} == {"success", "blocked"}
            for span in spans:
                assert span.end_time > span.start_time
                assert span.attributes["handoffguard.operation"] == "createOrder"
                # Missing untrusted trace header gets a fresh server UUID4.
                assert len(span.attributes["handoffguard.workflow_trace"]) == 36
                assert len(f"{span.context.trace_id:032x}") == 32
                assert "product_code" not in str(span.attributes)
            events = [json.loads(row.getMessage()) for row in caplog.records
                if row.name == "handoffguard.observability"
                and row.getMessage().startswith('{"schema":"handoffguard.observability.v1"')]
            assert len(events) == 2
            assert trace in {row["workflow_trace_id"] for row in events}
            assert len({row["workflow_trace_id"] for row in events}) == 2
            assert {row["workflow_trace_id"] for row in events} == {span.attributes["handoffguard.workflow_trace"] for span in spans}
            assert {row["otel_trace_id"] for row in events} == {
                f"{span.context.trace_id:032x}" for span in spans
            }
            assert all(len(row["request_id"]) == 36 for row in events)
            serialized = json.dumps(events) + repr([s.attributes for s in spans])
            assert SYNTHETIC_TOKEN not in serialized
            assert SYNTHETIC_PAYLOAD["product_code"] not in serialized
    finally:
        logger.removeHandler(caplog.handler)


def test_telemetry_failure_never_breaks_order_api(client, headers, caplog):
    """Failure of an optional local collector cannot corrupt a business response."""
    class BrokenLab:
        def record(self, *_args, **_kwargs):
            raise RuntimeError("SYNTHETIC-PRIVATE-TRANSPORT-SECRET")

    client.app.state.telemetry_v2 = BrokenLab()
    logger.addHandler(caplog.handler)
    try:
        response = client.post("/api/v1/orders", headers=headers["sales"], json=SYNTHETIC_PAYLOAD)
        assert response.status_code == 201
        assert "X-Request-ID" in response.headers
        texts = "\n".join(record.getMessage() for record in caplog.records)
        assert "telemetry_export_suppressed" in texts
        assert "SYNTHETIC-PRIVATE-TRANSPORT-SECRET" not in texts
    finally:
        client.app.state.telemetry_v2 = None
        logger.removeHandler(caplog.handler)
