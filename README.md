# HandoffGuard AI

**DataTalks.Club AI Dev Tools Zoomcamp 2026 — Project 1**

> **Status:** Backend Gate 02 merged; Frontend Gate 03 merged into main. Not deployed. Synthetic educational demo only.

HandoffGuard AI controls commercial changes to manufacturing orders. Sales may propose revised quantity/terms, production records feasibility, an authorized approver accepts or rejects, sales records a matching customer agreement, and only then may the server atomically create the next approved revision.

**Invariant:** customer messages, AI-generated text, or sales requests must not directly modify approved orders or pause production.

## Architecture

```text
Browser (React + TypeScript)
          ↓ typed client: frontend/src/api.ts
        /api/v1
          ↓ bearer authorization enforced on server
FastAPI (backend/app/main.py)
          ↓ SQLAlchemy, revision compare-and-swap
SQLite (local/testing) — PostgreSQL validation pending
```

- **Backend Gate 01/02:** Order, immutable-by-workflow revision snapshots, Change, ProductionReview, ApprovalDecision, CustomerAcceptance, impact assessment. Numeric amounts are stored as integer kopeks; missing estimated cost stays unknown.
- **Frontend Gate 03 (merged PR #3):** React, TypeScript, Vite, centralized API client, explicit user-controlled approval stages, version history, component/API tests.
- **Security scope:** synthetic local tokens for three roles (sales, production, approver). They must not be treated as production authentication or deployed as a public login interface.

## Run

1. Follow [backend/README.md](backend/README.md) and start FastAPI at `http://127.0.0.1:8000` with **synthetic** local role tokens.
2. In a second terminal, run the React frontend:

```sh
cd frontend
npm ci
npm run dev
```

3. Open `http://127.0.0.1:5173`, enter demo credentials, and walk through creating V1 → production review → change assessment → approver decision → customer acceptance → V2.

Vite proxies `/api` to the local backend. For documentation and limits see [frontend/README.md](frontend/README.md).

## Automated tests

```sh
cd backend
python -m pip install -e . pytest httpx pyyaml
python -m pytest -q
cd ../frontend
npm ci
npm test
npm run build
```

Backend checks are in `.github/workflows/backend-ci.yml`; frontend build/test checks are in `.github/workflows/frontend-ci.yml`.

## AI-assisted development evidence

- [Product specification](product-spec.md)
- [System decision record](docs/decision-record.md)
- [AI development workflow](docs/ai-development-workflow.md)
- [Frontend Gate 03 review record](docs/frontend-gate03-verification.md)
- [Golden synthetic scenarios](fixtures/golden-cases.json)
- [OpenAPI contract](openapi.yaml) (contains a planned source-ingestion route not yet implemented)
- [Project instructions](AGENTS.md)

## Known gaps before course submission

- Automated browser E2E tests (manual browser verification passed).
- PostgreSQL migration/integration, production-grade authentication, public deployment and CI/CD deploy.
- Observability, agent extension pack, security audit artifacts.

**Not production ready.** No real customer records, production integration or claimed financial ROI.

For exact course rules and deadlines use the official [DataTalks.Club project page](https://datatalksclub.github.io/docs/courses/ai-dev-tools-zoomcamp/project/) and the cohort platform.

## Docker Compose — Gate 04

HandoffGuard AI runs locally using Docker Compose.

### Start

1. Install Docker and Docker Compose.
2. Create a local `.env` with `HANDOFFGUARD_AUTH_TOKENS` for the three synthetic roles.
3. Run `docker compose up --build -d`.
4. Open http://127.0.0.1:8080 in a browser.

React is served by Nginx. Requests to `/api/` are forwarded
to FastAPI inside the Docker network.

### Database persistence

SQLite is stored in the named Docker volume `gate04_data`.
The existing local `backend/handoffguard.db` is not mounted
into the containers.

### Verification

Run `docker compose ps` to check both services.

An unauthenticated request to `/api/v1/orders/test`
must return HTTP 401.

Manual testing confirmed that the synthetic test order
remains available after restarting the containers.

### Stop

Use `docker compose down` to stop the services.
Do not use `docker compose down -v` when preserving data.

This configuration is for local synthetic testing only.
It is not production authentication or a public deployment.
