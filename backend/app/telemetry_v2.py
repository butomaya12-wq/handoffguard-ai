"""Opt-in local-only metrics and real OpenTelemetry operation spans.

Absent on the default Docker stack and cloud. Fixed low-cardinality labels;
never export tokens, path parameters, request bodies, errors or customer data.
"""
import os


class TelemetryV2:
    """One per-app provider/registry, not a global OpenTelemetry install."""

    @classmethod
    def from_environment(cls, *, cloud_mode: bool = False):
        if os.getenv("HANDOFFGUARD_OBSERVABILITY_V2_ENABLED", "") != "1":
            return None
        if cloud_mode:
            raise RuntimeError("Local observability lab cannot be enabled in the cloud demo")
        endpoint = os.getenv("HANDOFFGUARD_OTLP_TRACES_ENDPOINT", "")
        # Deliberately restrict exporter egress to the single local lab collector.
        if endpoint != "http://jaeger:4318/v1/traces":
            raise RuntimeError("Local observability lab requires the isolated Jaeger collector")
        return cls(endpoint)

    @staticmethod
    def _make_exporter(endpoint):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        return OTLPSpanExporter(endpoint=endpoint, timeout=0.5)

    def __init__(self, endpoint: str):
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from prometheus_client import CollectorRegistry, Counter, Histogram
        from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

        self._metrics_media_type = CONTENT_TYPE_LATEST
        self._registry = CollectorRegistry(auto_describe=True)
        self._counter = Counter(
            "handoffguard_business_operations_total",
            "Finished allowlisted business POST operations",
            ("operation", "outcome", "status_class"),
            registry=self._registry,
        )
        self._duration = Histogram(
            "handoffguard_business_operation_duration_seconds",
            "Measured elapsed time for an allowlisted business POST operation",
            ("operation", "outcome", "status_class"),
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
            registry=self._registry,
        )
        self._provider = TracerProvider(resource=Resource.create({
            "service.name": "handoffguard-local-observability",
            "deployment.environment": "local-synthetic",
        }))
        self._provider.add_span_processor(BatchSpanProcessor(
            self._make_exporter(endpoint),
            max_queue_size=256,
            max_export_batch_size=16,
            schedule_delay_millis=2000,
            export_timeout_millis=1000,
        ))
        self._tracer = self._provider.get_tracer("handoffguard.business-operations")

    def record(self, event: dict, *, started_ns: int, ended_ns: int) -> str:
        """Store safe counter/histogram and a bounded real SDK span for one action.

        The request is already complete when recorded; start/end nanoseconds
        refer to the actual recorded request interval. Each request has its
        own real OTel trace ID. workflow_trace_id is only a per-tab correlation
        HINT between related requests and never an auth identity.
        """
        operation = event["operation"]
        outcome = event["outcome"]
        status = event["http_status"]
        status_class = f"{status // 100}xx"
        labels = (operation, outcome, status_class)
        self._counter.labels(*labels).inc()
        # Explicit span attributes are allowlisted; no raw request or error text.
        span = self._tracer.start_span(
            operation,
            start_time=started_ns,
            attributes={
                "handoffguard.operation": operation,
                "handoffguard.outcome": outcome,
                "handoffguard.workflow_trace": event["workflow_trace_id"],
                "http.response.status_code": status,
            },
        )
        trace_id = f"{span.get_span_context().trace_id:032x}"
        span.end(end_time=ended_ns)
        # Exemplars associate one sample with its real OTel trace without adding
        # unbounded trace-ID labels to the Prometheus time series.
        self._duration.labels(*labels).observe(
            event["duration_ms"] / 1000.0, exemplar={"trace_id": trace_id}
        )
        return trace_id

    def metrics_text(self) -> bytes:
        from prometheus_client.openmetrics.exposition import generate_latest
        return generate_latest(self._registry)

    @property
    def metrics_media_type(self):
        return self._metrics_media_type

    def shutdown(self):
        self._provider.shutdown()
