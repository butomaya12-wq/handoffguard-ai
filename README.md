# HandoffGuard AI

**DataTalks.Club AI Dev Tools Zoomcamp 2026 — Project 1**

> **Status (2026-10-18):** Backend, frontend, Docker and one-command Testing Gate merged into `main`. PostgreSQL and private cloud-image CI verification is underway in [draft PR #12](https://github.com/butomaya12-wq/handoffguard-ai/pull/12). **No public deployment exists.** Synthetic educational demo only.

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
SQLite (local/Compose) / PostgreSQL (disposable CI integration verified in Gate 05)
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

Vite proxies `/api` to the local backend. For documentation and limits see [frontend/README.md](frontend/README.md). For a single-command full-stack local start, use the [Docker Compose instructions](#docker-compose--gate-04) below.

## Automated tests — one command

**Prerequisites:** Bash, Python 3.11+ with `venv` and `pip`, Node.js 22 and npm. From the **repository root**, on a clean checkout, install dependencies once:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e ./backend 'pytest>=8,<10' httpx pyyaml
(cd frontend && npm ci)
```

Then run **all backend tests, frontend tests and the React production build** with one command:

```sh
bash scripts/test-all.sh
```

The runner selects `backend/.venv/bin/python` if present, otherwise a root `.venv/bin/python` or the system `python3`. Override with `HANDOFFGUARD_TEST_PYTHON` if necessary. It uses `set -euo pipefail` and exits nonzero on any failed stage: **it never silently skips a suite or prints PASS after a failure**. Dependencies must already be installed; missing `pytest` or `node_modules` is a setup error, not a passing test. The backend API tests use temporary synthetic SQLite files; the script does not run migrations or delete application databases/Compose volumes. The frontend build writes ignored files under `frontend/dist/`.

On the developer Mac, the first attempt failed because `pytest` was missing from the backend venv; after installing dependencies, the same command reported **30 backend tests passed, 8 frontend tests passed, and a successful React build** (see [Issue #9 local evidence](https://github.com/butomaya12-wq/handoffguard-ai/issues/9)). One Starlette/httpx deprecation warning was emitted, not a failing test. These historical counts are not a claim about future runs.

CI executes **the same `bash scripts/test-all.sh`** from a clean checkout and also verifies that an intentionally failing backend command makes the runner exit unsuccessfully: [full-stack workflow](.github/workflows/full-stack-ci.yml). Existing independent checks remain in [backend CI](.github/workflows/backend-ci.yml), [frontend CI](.github/workflows/frontend-ci.yml), and [Docker Compose CI](.github/workflows/docker-ci.yml).

## AI-assisted development evidence

- [Product specification](product-spec.md)
- [System decision record](docs/decision-record.md)
- [Development agent roles, responsibility boundaries and task handoffs](docs/agent-team-and-handoffs.md)
- [Public submission acceptance tracker — Issue #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6)
- [Scoped agent team / context task — Issue #7](https://github.com/butomaya12-wq/handoffguard-ai/issues/7)
- [Historical Gate 01 AI development workflow](docs/ai-development-workflow.md)
- [Historical Frontend Gate 03 review record](docs/frontend-gate03-verification.md)
- [Merged Docker Gate 04 PR #5](https://github.com/butomaya12-wq/handoffguard-ai/pull/5) and [passing Docker CI smoke](https://github.com/butomaya12-wq/handoffguard-ai/actions/runs/39047520377)
- [Golden synthetic scenarios](fixtures/golden-cases.json)
- [OpenAPI contract](openapi.yaml) (contains a planned source-ingestion route not yet implemented)
- [Project instructions and context routing](AGENTS.md)
- [Gate 05 cloud architecture proposal](docs/cloud-gate05-design.md) and [deploy/rollback runbook](docs/cloud-gate05-runbook.md) — preflight evidence, **not** a public URL

Historical verification records reflect **the implementation at the time of that gate**, not the current overall readiness of HandoffGuard AI. The current submission tracker and CI results are the evidence index.

## Known gaps before course submission

- Automated browser E2E tests (manual browser verification passed). The root-level test runner and failure-path check were verified in [GitHub Actions](https://github.com/butomaya12-wq/handoffguard-ai/actions/runs/39062476710).
- Hosted managed PostgreSQL connection/retention, verified reviewer access on public HTTPS, public deployment, CI/CD deploy and rollback. PostgreSQL CI tests and Docker cloud-image smoke exist in draft [PR #12](https://github.com/butomaya12-wq/handoffguard-ai/pull/12), but do not prove hosted service readiness.
- Correlated observability, impact alerting, safe on-call responder agent and security/release audit evidence.
- Final reviewer-ready submission and three mandatory peer reviews.

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
