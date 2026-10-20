# Observability v2: scoped implementation plan (Issue #29)

**Status: DESIGN PROPOSAL ONLY — instrumentation, collectors, UI and evidence are NOT implemented by this document.**
**Repository base:** `main` at `3de22dcf98cc544d70ca88148af1388c22706900`.
**Owner-approved scope:** investigate and build *locally in an isolated draft branch*; no merge, cloud deploy, paid product, Render environment/config change, Neon access, customer data or unguarded remediation.

## 1. Course rubric and truthful baseline

The [2026 final project rubric](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md) awards 2 points for a key user journey instrumented with **metrics, traces, and structured logs with a shared trace ID**, free of customer data/credentials and collected, stored and viewable in a UI.

Existing `backend/app/observability.py` already emits an allowlisted JSON `business_operation_completed` record per tracked POST: validated UUIDv4 `workflow_trace_id` (browser-tab correlation hint), server `request_id`, operation name, coarse outcome, status, duration and *single event* `business_operation_total=1`. The events are searchable in Render Logs, and the tested synthetic V1→V2 workflow emits 10 correlated events. This is substantial observability work, **not zero**.

Missing for robust 2-point evidence: real bounded counter/latency metric series and readable stored span timelines. **The `Обзор` business analytics screen is not the operations observability screen.** Do not promise the rubric score before a reviewer can reproduce all three views.

## 2. Small, isolated local stack

| Component | Choice and boundaries |
| --- | --- |
| Backend spans | Optional, explicit `HANDOFFGUARD_OBSERVABILITY_V2_ENABLED=1`. OpenTelemetry SDK + OTLP HTTP exporter, only allowlisted business POST operations. Opt-in dependency extra; **off by default** in current cloud and ordinary Compose. |
| Backend metrics | Actual counters and duration histograms with bounded `operation`, `outcome`, and status class attributes only. Prometheus-compatible text endpoint reachable only on an isolated Docker-internal network when v2 enabled; no anonymous public endpoint. |
| Traces viewer | Pinned self-hosted Jaeger all-in-one with OTLP receiver, persistent Badger named volume and 24–72 h TTL (confirm image/version and non-root volume permissions in implementation). Jaeger UI published on **127.0.0.1 only**. |
| Metrics viewer | Pinned Prometheus instance scraping only backend's local metrics endpoint. Named volume, short retention (e.g. 24 h), bounded storage and port **127.0.0.1:9090 only**. |
| Logs | Keep current redacted JSON business logs in Docker stdout (`docker compose logs`) and Render Logs for the existing published version; no new third-party log collector. |
| Deployment | Add a **separate opt-in Docker Compose observability override**, not modifications to the default workflow or Render config. Avoid reliance on the `docker.sock`, privileged containers or host network. |

No personal/customer text, raw HTTP route/URL/query, order/change IDs, bearer token, cookie, DB DSN, raw exception or headers in spans, metric attributes or exporter errors. `operation` comes solely from the existing allowlist; do not record arbitrary labels. Do not expose `/metrics` from the Render deployment.

**Important trace semantics:** `X-Workflow-Trace` is a *client-generated, untrusted per-browser-tab UUID4* and can cover multiple orders; it is **not a verified one-order trace**. A true OpenTelemetry span must have an actual `SpanContext`; do not rename the existing JSON correlation field “distributed tracing” and do not use its value to grant authority. For a deterministic multi-request demo either create safely correlated spans through an explicitly validated context or present real per-request trace IDs and a distinct workflow correlation attribute, explaining the difference. Ideally the log includes the actual OTel trace ID alongside the workflow hint when v2 is on, allowing reviewers to navigate between a log event and Jaeger. Do not put either trace ID into Prometheus time-series *labels*, as that creates cardinality explosion; exemplars, if supported, may attach sparse trace links to duration samples.

## 3. Proposed implementation order — each has an executable gate

1. **Backend unit only.** Introduce an optional, fail-open telemetry adapter recording an actual OTel span for one allowlisted business POST and an actual counter/duration histogram; do not change `status_code`, body or business decisions. Prove trace/log consistency and negative redaction. Absent/down exporter must never fail or slow business requests beyond a bounded timeout.
2. **Local collection.** Add Prometheus/Jaeger sidecars with named volumes, loopback-only UI, explicitly opted-in backend image; smoke test off-by-default behaviour and no changes to existing Docker default. Validate exporter and readiness; use pinned, verified image tags.
3. **One genuine synthetic flow.** From a fresh local clone, create V1=100, production review, V2 proposed 120, assessment, submit, approver approve, synthetic customer acceptance, apply V2. Capture (a) structured correlated stdout events, (b) increasing Prometheus request totals and latency histogram, and (c) actual Jaeger spans with matching correlation evidence and retained samples after service restart. Include at least one **expected 403/409** distinguished from an actual 5xx.
4. **Security/failure tests.** Missing optional deps/flag, invalid trace, exporter outage, arbitrary text and secrets, unauthorized/overbroad metrics endpoint, metric label cardinality; never emit real UUIDs/order IDs as metrics attributes. Verify existing `bash scripts/test-all.sh`, five PR CI workflows, clean clone/Compose docs and owner Mac screenshot.
5. **Owner acceptance before release.** Collect links to exact CI SHA, run/test outputs, screenshots, technical limitations, and review all modifications. Keep this as a **Draft PR**. No automatic or manual Render deploy, main merge, Neon writes or change to business auth until specifically authorized.

## 4. User-impact alerting and future on-call agent

Criterion 11's current threshold alert remains unchanged (real 5xx on create/apply, rolling count, best-effort Telegram). It is not a durable pager. Criterion 12 is a distinct [Issue #28](../issues/28) and is **not implemented**.

Before building on-call remediation:
- Decide on an isolated **real, reversible, fixed-action** failure; no cloud, production DB, or real customer state. Example: a disposable local health-probe worker stops and can be safely restarted by a constrained *single allowlisted* action. Do not give unrestricted Docker socket or shell to an LLM.
- Prove `healthy → deliberately unhealthy → alert delivered → agent activated → fixed action → independently healthy` with time-stamped evidence.
- Keep the agent default read-only; network, deploy, restart or business-data mutation of any non-disposable live system requires the owner's explicit review.
- If the system only diagnoses or proposes a fix, mark the on-call criterion **INCOMPLETE** rather than fabricate recovery.
- Review the course submission and mandatory three peer reviews before spending time on the optional 2 points.

## 5. Stop/go and acceptance

The locally confirmed baseline is 52 backend + 17 frontend tests on the separate UI branch PR #27; **these are not test results for this design branch**. Never present them as such. Define short staged checks before claiming a new PASS. If the local stack adds unacceptable download, memory or demo-access friction, halt and preserve rubric #10 partial evidence rather than jeopardize submission.

Useful documentation:
- [OpenTelemetry Python exporters](https://opentelemetry.io/docs/languages/python/exporters/)
- [Jaeger single-node storage](https://www.jaegertracing.io/docs/1.76/deployment/)
- [Final project criteria](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md)
