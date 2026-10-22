# Observability v2 — isolated local reviewer lab

**Status:** implementation candidate in Draft PR #30; do **not** claim final 2/2 until Mac + CI evidence demonstrates both UI backends with actual measurements.

This lab deliberately runs **alongside** the default HandoffGuard Docker Compose and maintains its own SQLite, Prometheus and Jaeger named volumes. No Render/Neon or hosted demo credentials are used or altered.

## Starting only the lab

Prerequisites: Docker Desktop/Compose and an ignored repository-root `.env` with **synthetic local** `HANDOFFGUARD_AUTH_TOKENS` for sales, production and approver (see root README). Never reuse hosted reviewer/role credentials.

From the repository root, while on the branch containing this lab:

```bash
docker compose -f docker-compose.observability.yml config -q
docker compose -f docker-compose.observability.yml up --build -d --wait
docker compose -f docker-compose.observability.yml ps
```

It is a **separate Compose project** named `handoffguard-observability-lab`, not a replacement for `handoffguard-gate04-compose`.

| UI | Loopback-only URL | What should be visible |
| --- | --- | --- |
| Synthetic app | http://127.0.0.1:8082 | Full local workflow on its separate empty test database |
| Prometheus | http://127.0.0.1:9090 | `handoffguard_business_operations_total` and `handoffguard_business_operation_duration_seconds` series after operations (scrapes every 5 s) |
| Jaeger | http://127.0.0.1:16686 | Service `handoffguard-local-observability` and real SDK operation spans after export delay (normally 2 s) |

Use **new, clearly labeled synthetic orders only**. Example: role sales creates V1=100, production checks, sales proposes V2=120, assesses/submits, approver approves, sales records **synthetic** customer acceptance, approver applies. Check browser and Render are not being mixed up: the lab's test UI uses **8082**, while the normal local app uses **8080**, and hosted HTTPS is a separate deployment.

The metric series only have **three bounded labels:** `operation`, `outcome`, and `status_class`. A duration-histogram **OpenMetrics exemplar** carries the actual 32-character Jaeger `trace_id` for a sampled observation (not a time-series label); Prometheus is explicitly configured with `--enable-feature=exemplar-storage`. Match the exemplar to the safe JSON log `otel_trace_id` and Jaeger trace ID. The 24-hour series retention and bounded in-memory exemplar buffer are not permanent storage. No raw product, order, customer, token, URL, ID or trace identifiers are series labels. Query e.g.:

```promql
sum by (operation, outcome) (handoffguard_business_operations_total)
```

```promql
rate(handoffguard_business_operation_duration_seconds_sum[5m])
/
rate(handoffguard_business_operation_duration_seconds_count[5m])
```

The tracing view contains a true `otel_trace_id` **per request**; the local JSON business log carries the matching `otel_trace_id` and a separate `workflow_trace_id` hint shared by requests in the same browser tab. **Do not mislabel this as one verified trace per individual order**: a browser tab may operate on more than one. Open Jaeger spans by actual trace ID and review safe attributes `handoffguard.operation`, `handoffguard.outcome`, `handoffguard.workflow_trace` and `http.response.status_code`.

Read the lab backend stdout:

```bash
docker compose -f docker-compose.observability.yml logs backend --tail=50
```

**Retention:** Prometheus runs with a 24-hour timeseries TTL and a dedicated Docker volume; Jaeger Badger storage has a 24-hour span TTL and a dedicated volume. Both UIs bind **only** to localhost. Logs stay within the local Docker engine. Default Docker Compose has no `/internal/metrics` service and the remote cloud demo refuses any local lab activation.

Stop safely, preserving the test history:

```bash
docker compose -f docker-compose.observability.yml down
```

Do **not** use `down -v` unless you intentionally want to destroy **only** the lab's named volumes. Never run container commands against Render or Neon for this demonstration.

## Honest limits

- This is a single-node educational OpenTelemetry/Prometheus/Jaeger lab; not persistent cloud monitoring or end-to-end distributed propagation through multiple services.
- The existing best-effort Telegram alert is separate. A 401/403/409 is a normal rejected operation, **not** automatically an outage.
- The spans are recorded retrospectively using the real backend request timing, one span per tracked business POST. They do not instrument SQL internals or reproduce a multi-service parent-child span tree.
- The OTLP exporter runs asynchronously with bounded queue and timeout; the optional stack may drop telemetry if unavailable, but must not fail business operations.
- Reviewer access to local UIs requires the reviewer to run the lab on their own machine; the hosted Render app has no Jaeger/Prometheus UIs. This is a limitation for the course grader that must be clearly documented.
- Jaeger v1 all-in-one 1.76 is chosen specifically for documented single-node Badger storage; it is **not** the latest cloud-recommended Jaeger architecture. Future evolution could use Jaeger v2 + a separately configured storage/collector.
- Criterion 12 **has a separate, proven one-shot local agent recovery experiment** under [Issue #28](../issues/28) and [Draft PR #32](https://github.com/butomaya12-wq/handoffguard-ai/pull/32): after two Prometheus down scrapes, a real OpenAI analysis and separate session preauthorization permitted one fixed lab backend start and independent health verification. This is **not** part of hosted Render or an unattended responder. See [owner UAT](oncall-autorecover-owner-uat-2026-10-22.md). A diagnostic notification alone is not an agent fix.

## Evidence checklist

- [ ] GitHub optional-dependency backend tests pass (real in-memory exporter checks spans and matched JSON trace ID).
- [ ] Default CI all green; only opt-in lab is modified.
- [ ] Docker Compose `config -q` and lab startup run on Mac without touching the default local `8080` app.
- [ ] Prometheus scrape target UP and real `createOrder` counters after synthetic POST; increasing count and duration histogram seen on-screen.
- [ ] Jaeger service and real `createOrder` span; match Jaeger trace ID to the safe log's `otel_trace_id`.
- [ ] Controlled failure of exporter does not modify business HTTP response; no secrets or raw text leak.
- [ ] At least one full V1→V2 case captured with logs, metrics and spans. Store proof in Issue #29.
- [ ] Independent owner signoff before any merge or release.
