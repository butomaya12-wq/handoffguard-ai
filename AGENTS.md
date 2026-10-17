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
- **Containers:** `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `.github/workflows/docker-ci.yml`.
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

## Current implementation (2026-10-17)

- **Backend Gate 01/02 merged:** FastAPI + SQLAlchemy/SQLite, approved order V1/V2, change impact, human production review, fingerprint-bound internal approval, verified recorded customer agreement and persistence; backend API tests.
- **Frontend Gate 03 merged ([PR #3](https://github.com/butomaya12-wq/handoffguard-ai/pull/3)):** React + TypeScript, centralized API client, browser-tested V1→V2 and Vitest tests.
- **Docker Gate 04 merged ([PR #5](https://github.com/butomaya12-wq/handoffguard-ai/pull/5)):** Compose for frontend/backend/SQLite, Nginx proxy, named DB volume; Docker CI smoke passed.
- **Gate 05 underway:** safe cloud deployment, secure access and persistent hosted database. **Not publicly deployed** as of this update.
- **Still pending or limited:** PostgreSQL verification, public demo, CI/CD deployment and rollback, one-command all-tests runner, telemetry/alerting, on-call responder agent, automated browser E2E, mature production auth, and peer reviews.

**Scope disclaimer:** An educational local synthetic demo is **not production-ready**. Existing local role tokens must never be used as public authentication. Historical Gate 01/03 notes capture their contemporary status, not the current overall status.
