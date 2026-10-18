# Gate 06 — minimal business observability (Issue #16)

**Status:** candidate implementation on `feature/observability-issue16`; not deployed or approved for merge.
**Scope:** synthetic HandoffGuard business workflow; no tenant identity or real-customer telemetry.

## How to trace a user action

The React API client stores a cryptographically random **UUIDv4** in per-tab `sessionStorage` (key `handoffguard-workflow-trace`), and submits it in `X-Workflow-Trace` with every API call. It is a non-secret, client-controlled correlation **hint**, not an authenticated identity, proof of authorization or verified one-order trace. It is reused while the same browser tab session remains open (even when a different order is loaded). A new tab normally gets a new trace; copied tab state may inherit storage. Server accepts only *canonical UUIDv4*; invalid or missing values are discarded and replaced with a new server UUIDv4 **per request**, which cannot magically correlate separate clients.

FastAPI generates a unique `request_id` UUIDv4 for each request. For tracked business POST operations it adds the `X-Request-ID` response header and emits one allowlisted JSON event on stdout. Search Render **Logs** for `business_operation_completed` or a safe `workflow_trace_id` value. The joined event chain covers real API actions, e.g.:
`createOrder → recordProductionReview → createChange → assessChange → submitForApproval → decideChange → recordCustomerAcceptance → applyApprovedChange`.

Only these eight server route operation IDs are tracked. Authentication failures *inside* the business API are tracked on a matched route; rejections by the **outer reviewer cookie gate** happen earlier and are deliberately **not** logged as business operations. GETs, login forms and health checks are omitted. A single flow has distinct request IDs but the same workflow trace ID when the browser supplies it.

## Log schema and log-derived metrics

One JSON stdout event has exactly the following **allowlisted** fields, with no raw path/params or payload:

| Field | Meaning |
|---|---|
| `schema` | `handoffguard.observability.v1` |
| `timestamp_utc` | UTC ISO 8601 time |
| `event` | `business_operation_completed` |
| `workflow_trace_id` | validated canonical UUIDv4 |
| `request_id` | server-generated UUIDv4 |
| `operation` | one of eight known FastAPI operation IDs |
| `outcome` | `success` (2xx/3xx), `blocked` (401/403/409/422), `client_error` (other 4xx), `failure` (5xx) |
| `http_status` | numeric HTTP status |
| `duration_ms` | nonnegative wall-clock processing time, milliseconds |
| `metric_name` | `business_operation_total` |
| `metric_value` | 1 for each emitted operation event |

The value **1** is a *single observed completion*, not a running or durable counter. Count events grouped by `operation`, `outcome` over a chosen time range; calculate latency distributions from `duration_ms`. A business-blocked 409 or access-protecting 403 is **not** a platform incident. An event reporting 500 is a meaningful application failure but does not by itself demonstrate customer impact severity. Event completion is not proof of a committed business transaction when an internal exception occurs.

Illustrative event **schema only; not evidence of running production telemetry**:
```json
{"schema":"handoffguard.observability.v1","timestamp_utc":"2026-10-18T00:00:00+00:00","event":"business_operation_completed","workflow_trace_id":"123e4567-e89b-42d3-a456-426614174000","request_id":"e3801a1a-164c-4875-8f6c-b31fffc160aa","operation":"createOrder","outcome":"success","http_status":201,"duration_ms":8.75,"metric_name":"business_operation_total","metric_value":1}
```
*The timestamps/IDs/numbers in the illustrative example are not measured results.*

## Secrets and cloud limitations

- The logger never emits `Authorization` headers, reviewer cookies/access keys, bearer tokens, actors, raw URLs with IDs, arbitrary HTTP headers, request/response bodies, customer evidence or source text, SQL connection URLs or exceptions. Server-side role checks remain unchanged.
- Only canonical UUIDv4 is accepted as a trace ID; **never paste real credentials into log search**.
- The cloud Uvicorn launch turns off **raw access logs** with `--no-access-log` because they can include private URL path parameters. The allowlisted business JSON event log is independent and stays enabled. Local Docker Compose continues using its existing Uvicorn defaults; ensure no real customer data is supplied to it.
- Logs are sent to ordinary stdout and viewed through the existing **Render Free** log viewer. There is **no metrics database, sampling, guaranteed retention, durable aggregation, distributed span tracing, paid instrumentation vendor, error notification or SLA**.
- `/health` continues to report liveness, not PostgreSQL readiness. Client correlation can be spoofed or repeated and must never grant privileges.

## Verification gates

1. Branch/PR CI: backend synthetic V1→V2 tests verify actual event chain, matched workflow UUID, distinct request UUID, 403 and 409 blocked outcomes, metric field/units and secret redaction; frontend Vitest checks reused UUID and no role token in correlation header. Existing runner `bash scripts/test-all.sh` and all five CI workflows must remain green.
2. **Owner** runs root `bash scripts/test-all.sh` on the PR branch and reviews test/JSON log evidence. Synthetic tests use disposable SQLite; GitHub's existing Postgres CI uses disposable PostgreSQL.
3. **Human approval required to merge.** Review Render Free plan, current live code, automatic-deploy implications and database safety before merging to `main`; a merge can trigger automatic cloud deploy because CD is enabled. Do not claim hosted JSON logs until the merged deployment is actually observed and inspected without secrets.
4. Close rubric **10 Observability** only after a real captured synthetic journey (test + if deployed, safe Render logs) and recorded, redacted evidence. Criterion **11 Alerting** needs a separate design/approval.
