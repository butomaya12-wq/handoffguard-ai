# AI coding-assistant instructions — HandoffGuard AI

**Project:** DataTalks.Club AI Dev Tools Zoomcamp 2026 Project 1.  
**Task tracker:** [submission #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6) and scoped implementation issues (starting with [#7](https://github.com/butomaya12-wq/handoffguard-ai/issues/7)).  
**Team / handoffs:** [docs/agent-team-and-handoffs.md](docs/agent-team-and-handoffs.md).

## Invariants that must never be violated

- A client request is **not** an approved order change.
- An AI model never approves, applies, or stops production.
- Pending changes do not modify the current approved order revision.
- Production feasibility is verified by an authenticated production reviewer.
- Only the authenticated single authorized company approver may internally approve.
- Internal approval is not customer acceptance; both are needed to apply.
- Approval refers to an immutable impact-assessment fingerprint. Stale inputs invalidate prior authorization.
- Missing economic inputs are UNKNOWN, not zero; money uses integer kopeks.
- A completed order is not changed/applied in the MVP.
- Maintain provenance and immutable version/audit history; reject unsupported operations.

## Required context and navigation

Always start with the scoped **GitHub Issue**, this file and [product-spec.md](product-spec.md). Load other documents based on the task rather than pasting the entire repository:

- **Business rules and authority:** [architecture decisions](docs/decision-record.md), [golden synthetic cases](fixtures/golden-cases.json).
- **API / backend:** [OpenAPI draft](openapi.yaml), `backend/app/main.py`, `backend/app/schemas.py`, `backend/tests/`. OpenAPI includes a **planned source-ingestion route**; do not claim every documented route exists.
- **Frontend:** `frontend/src/api.ts`, `frontend/src/App.tsx`, [frontend setup](frontend/README.md), [historical Gate 03 verification](docs/frontend-gate03-verification.md).
- **Containers and cloud preflight:** local `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `.github/workflows/docker-ci.yml`; cloud-only `Dockerfile.cloud`, `backend/app/cloud.py`, [Gate 05 design](docs/cloud-gate05-design.md), [safe deploy runbook](docs/cloud-gate05-runbook.md), `.github/workflows/postgres-ci.yml`.
- **Agent roles, handoffs, evidence:** [team and handoffs](docs/agent-team-and-handoffs.md), [Gate 01 AI workflow record](docs/ai-development-workflow.md), [historical verification](docs/gate-01-verification.md).
- **Submission criteria:** [official project rubric](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md), [submission issue #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6).

Business application roles (sales, production, approver) are distinct from the AI assistant's *development/review functions*. Those functions are not separately deployed autonomous agents.

## Development and evidence workflow

1. Read the **public task issue** with acceptance criteria; write a limited plan and review risks before changing code.
2. Implement one vertical slice on a feature branch; do not expand the MVP or invent integrations.
3. Keep frontend/backend calls aligned with **implemented** FastAPI routes; separately mark planned OpenAPI routes.
4. Add positive and negative automated tests for each business state transition. Prefer a test that fails before the fix and passes after.
5. Execute tests; record **real commands, CI run links and outcomes**. Do not claim a PASS based only on inspection.
6. Use fake/synthetic business records in the public repo. Never commit `.env`, real credentials, customer records or API keys.
7. Audit server-side role boundaries, stale fingerprints, persistence and secrets before a release.
8. Request explicit **human verification and merge approval**; record corrections, unresolved limits, task/PR links and handoff.
9. Update the task issue, relevant docs and submission tracker with evidence; distinguish historical records from current code.

## Current implementation (2026-10-18)

- **Backend Gate 01/02 merged:** FastAPI + SQLAlchemy/SQLite, approved order V1/V2, change impact, human production review, fingerprint-bound internal approval, verified recorded customer agreement and persistence; backend API tests.
- **Frontend Gate 03 merged ([PR #3](https://github.com/butomaya12-wq/handoffguard-ai/pull/3)):** React + TypeScript, centralized API client, browser-tested V1→V2 and Vitest tests.
- **Docker Gate 04 merged ([PR #5](https://github.com/butomaya12-wq/handoffguard-ai/pull/5)):** Compose for frontend/backend/SQLite, Nginx proxy, named DB volume; Docker CI smoke passed.
- **Testing Gate 06 merged ([PR #10](https://github.com/butomaya12-wq/handoffguard-ai/pull/10)):** `bash scripts/test-all.sh` runs backend pytest, frontend Vitest and production build on developer Mac and in CI (38 tests, historical result).
- **Gate 05 preflight underway ([draft PR #12](https://github.com/butomaya12-wq/handoffguard-ai/pull/12)):** optional psycopg, real disposable PostgreSQL integration, protected same-origin cloud Docker image and CI smoke across container restart. No Render/Neon deployment, public URL or live DB verification yet.
- **Still pending or limited:** actual hosted PostgreSQL/TLS and retention checks, live public-demo security/access validation, CI/CD deployment and rollback, telemetry/alerting, on-call responder agent, automated browser E2E, mature production auth, and three mandatory peer reviews.

**Scope disclaimer:** An educational local synthetic demo is **not production-ready**. Existing local role tokens must never be used as public authentication. Historical Gate 01/03 notes capture their contemporary status, not the current overall status.
