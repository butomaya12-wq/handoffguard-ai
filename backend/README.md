# Backend — Gate 01

Python 3.11+; FastAPI, Pydantic v2, SQLAlchemy. Local database: SQLite.

## Local tests

```bash
cd backend
python -m pip install -e . pytest httpx
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
| POST /api/v1/orders | sales | Create approved baseline revision 1 |
| GET /api/v1/orders/{order_id} | any known role | Get approved baseline; proposals cannot modify it |
| POST /api/v1/orders/{order_id}/production-reviews | production | Record progress/feasibility; invalidates previous assessments |
| POST /api/v1/orders/{order_id}/changes | sales | Create a non-binding proposal |
| GET /api/v1/changes/{change_id} | any known role | Read proposal lifecycle status |
| POST /api/v1/changes/{change_id}/assess | sales | Deterministic financial and feasibility assessment |
| POST /api/v1/changes/{change_id}/submit | sales | Submit current feasible assessment for internal approval |
| POST /api/v1/changes/{change_id}/decision | approver | Approve or reject, tied to exact assessment fingerprint |

`409` — state transition cannot proceed or assessment stale. `403` — authenticated role is not authorized. `401` — missing/invalid token. `422` — invalid input.

**Money amounts are integer kopeks.** Null estimated costs mean unknown, never zero. This backend does not ingest client documents or update factory execution.

## Still to implement

Customer acceptance and the actual revision-application endpoint; source evidence/audit trail, full OpenAPI coverage, PostgreSQL integration/migrations, frontend and deployment. These gaps are intentional at Gate 01, not hidden functionality.
