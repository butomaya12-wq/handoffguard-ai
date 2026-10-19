# Backend — Gate 02 (educational MVP)

Python 3.11+; FastAPI, Pydantic v2, SQLAlchemy. Local database: SQLite.

## Local tests

```bash
cd backend
python -m pip install -e . pytest httpx pyyaml
python -m pytest -q
```

Every test uses a separate temporary SQLite database and synthetic data. No external LLM call or API key is required. Alternatively use `uv sync` and `uv run pytest -q`.

## Start the local server

Configure **local-only** demo tokens in your terminal (replace each sample token with a unique value for your machine). Never commit a real token:

```bash
export HANDOFFGUARD_AUTH_TOKENS='{"local-sales-only":{"id":"sales-demo","role":"sales"},"local-production-only":{"id":"production-demo","role":"production"},"local-approver-only":{"id":"approver-demo","role":"approver"}}'
export HANDOFFGUARD_DATABASE_URL='sqlite:///./handoffguard.db'
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`. Select **Authorize** and enter a role's local token for that role's API calls.

These environment-token identities are for an educational demo, **not production-grade identity management**. Production requires a secure IdP/token lifecycle, role administration, rate limiting and a security review. `/health` is only a liveness response, not a DB readiness probe.

## Implemented API operations

| Operation | Required role | Behavior |
|---|---|---|
| POST /api/v1/orders | sales | Create approved baseline revision 1 |\n| GET /api/v1/orders/{order_id}/revisions | authenticated | Read approved snapshots V1, V2… |
| GET /api/v1/orders/{order_id} | any known role | Get approved baseline; proposals cannot modify it |
| POST /api/v1/orders/{order_id}/production-reviews | production | Record progress/feasibility; invalidates previous assessments |
| GET /api/v1/orders/{order_id}/changes | sales or approver | Read saved proposals, assessment snapshots and customer acceptance status to resume after refresh |
| POST /api/v1/orders/{order_id}/changes | sales | Create a non-binding proposal |
| GET /api/v1/changes/{change_id} | any known role | Read proposal lifecycle status |
| POST /api/v1/changes/{change_id}/assess | sales | Deterministic financial and feasibility assessment |
| POST /api/v1/changes/{change_id}/submit | sales | Submit current feasible assessment for internal approval |
| POST /api/v1/changes/{change_id}/decision | approver | Approve or reject, tied to exact assessment fingerprint |\n| POST /api/v1/changes/{change_id}/customer-acceptance | sales | Record matching customer terms and evidence attribution (not e-signature) |\n| POST /api/v1/changes/{change_id}/apply | approver | Conditional update and append next approved revision after both approvals |

`409` — state transition cannot proceed or assessment stale. `403` — authenticated role is not authorized. `401` — missing/invalid token. `422` — invalid input.

**Money amounts are integer kopeks.** Null estimated costs mean unknown, never zero. This backend does not ingest client documents or update factory execution.

## Migration and compatibility (important)

Existing Gate 01 SQLite database files may contain orders without V1 snapshots. `Base.metadata.create_all()` does not reconstruct old approval evidence. The app **refuses startup** if an existing order lacks a V1 record. Make a backup and perform a separately reviewed, evidence-backed data migration; do not delete the original database and do not invent approvals. There is **no automated migration/backfill in this PR**. New, empty demo databases start normally.

## Current hosted implementation and boundaries (2026-10-19)

The backend is deployed with the React frontend as a **single same-origin Docker service on Render Free**, with a distinct private reviewer session gate and **Neon PostgreSQL** persistence. The local backend/Compose configuration continues to use synthetic role tokens and SQLite. Read-only provider queries confirmed approved V1/V2, approval and customer acceptance survived hosted releases; see [Gate 05 provider verification](https://github.com/butomaya12-wq/handoffguard-ai/issues/11).

[Observability](app/observability.py) records correlated, redacted business operation events and log-derived measurements; [alerting](app/alerting.py) issues bounded best-effort Telegram alerts for repeated business 5xx (see [Issue #18](https://github.com/butomaya12-wq/handoffguard-ai/issues/18)). A safe opt-in diagnostic was received from the actual Render backend, then switched off; see [Issue #22](https://github.com/butomaya12-wq/handoffguard-ai/issues/22).

**Still not implemented / not proven for production:** verified individual customer identity, legal signatures, persistent tamper-evident audit service, full document/source ingestion (the draft OpenAPI source endpoint is planned), PostgreSQL load testing and migrations for arbitrary legacy data, tenant isolation or durable always-on alert counters. The five-repeat SQLite concurrency test is not proof against every race schedule. These omissions do not mean the already verified frontend, Docker Compose or hosted demo are still future work.

**Reader entrypoint:** [root README](../README.md), [product specification](../product-spec.md), [public acceptance tracker](https://github.com/butomaya12-wq/handoffguard-ai/issues/6).

