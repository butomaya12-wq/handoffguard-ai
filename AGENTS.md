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
- **Containers and cloud deployment:** local `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `.github/workflows/docker-ci.yml`; cloud-only `Dockerfile.cloud`, `backend/app/cloud.py`, [historical Gate 05 design](docs/cloud-gate05-design.md), [historical safe deploy/rollback runbook](docs/cloud-gate05-runbook.md), `.github/workflows/postgres-ci.yml`; [actual hosted evidence in Issue #11](https://github.com/butomaya12-wq/handoffguard-ai/issues/11).
- **Agent roles, handoffs, evidence:** [team and handoffs](docs/agent-team-and-handoffs.md), [Gate 01 AI workflow record](docs/ai-development-workflow.md), [historical verification](docs/gate-01-verification.md); [Issue #16 observability](https://github.com/butomaya12-wq/handoffguard-ai/issues/16), [Issue #18 alerting](https://github.com/butomaya12-wq/handoffguard-ai/issues/18), [Issue #22 diagnostic](https://github.com/butomaya12-wq/handoffguard-ai/issues/22).
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

## Current verified implementation (2026-10-19)

- **Business logic (merged):** FastAPI/SQLAlchemy, verified order V1/V2 history, production review, separate sales proposals, deterministic impact, fingerprint-bound human internal approval, matching recorded customer acceptance and authorized apply. AI does **not** autonomously approve or apply changes.
- **Frontend (merged [PR #3](https://github.com/butomaya12-wq/handoffguard-ai/pull/3)):** React/TypeScript, explicit role workflow, stored revision history, Vitest coverage, manual local and hosted user-journey evidence. Browser E2E is manual, not automated.
- **Local containers (merged [PR #5](https://github.com/butomaya12-wq/handoffguard-ai/pull/5)):** `docker compose up --build -d`, frontend Nginx proxy, backend FastAPI, persistent named SQLite volume. Uses **synthetic local-only credentials**.
- **Testing ([Issue #9](https://github.com/butomaya12-wq/handoffguard-ai/issues/9)):** `bash scripts/test-all.sh` runs pytest + frontend Vitest + TypeScript/Vite build; **owner verified 42 backend and 9 frontend PASS + build on Mac (2026-10-19)**; five GitHub workflows PASS for [PR #24](https://github.com/butomaya12-wq/handoffguard-ai/pull/24). Keep evidence tied to the actual commit.
- **Cloud, CI/CD ([Issue #11](https://github.com/butomaya12-wq/handoffguard-ai/issues/11)):** protected same-origin React/FastAPI Docker on Render Free over HTTPS, managed Neon PostgreSQL, separate signed reviewer cookie perimeter and three server-validated cloud-only synthetic role tokens; automatic deployment after CI checks and manually verified rollback. **Live on main `5d493d11608d55da48c93b066b68d946ad748f32` as of 2026-10-19**. This is a dated release observation; re-check Render after any newer merge.
- **Observability ([Issue #16](https://github.com/butomaya12-wq/handoffguard-ai/issues/16)):** real correlated and allowlisted JSON business-operation logs in Render Logs; log-derived metric samples, UUIDv4 workflow/request IDs. No durable external metrics store or guaranteed telemetry retention.
- **Alerting ([Issue #18](https://github.com/butomaya12-wq/handoffguard-ai/issues/18)):** best-effort in-process threshold for 3 matching business-operation 5xx in 5 minutes, 15-minute cooldown, safe Telegram notification. Threshold verified in isolated automated tests; **owner confirmed a diagnostic message sent from deployed Render backend was received** (linked [Issue #22](https://github.com/butomaya12-wq/handoffguard-ai/issues/22)). Diagnostic opt-in was reset to an empty value and cleanup Render deploy returned Live. Do not claim a real hosted 5xx incident or 24/7 coverage.
- **Still pending or intentionally excluded:** full source-ingestion/OCR and AI extraction runtime, automated browser E2E, production SSO/tenant isolation, external persistent metrics, autonomous on-call remediation (**rubric #12**), final course submission and **three required peer reviews**. Business workflow must remain unchanged through documentation polish.

**Reviewer-ready docs task:** [Issue #25](https://github.com/butomaya12-wq/handoffguard-ai/issues/25). **Single source of truth for current course checklists:** [Issue #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6). Historical reports and dated claims above must not be silently presented as fresh checks.

**Safety disclaimer:** Educational synthetic demo, **not production-ready**. Never paste or commit Render/Neon/Telegram/role/reviewer secrets. Never use local demo tokens as public authentication. Do not merge or publish PRs without explicit human approval. Do not alter existing approved Neon V1=100/V2=120 history during submission preparation.
