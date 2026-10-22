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

## Current verified implementation and release (2026-10-22)

- **Business logic in `main`:** FastAPI/SQLAlchemy, immutable approved order V1/V2 history, production feasibility review, separate sales proposals, deterministic impact, fingerprint-bound human internal approval, matching customer acceptance and authorized apply. An LLM does not autonomously approve or apply a business change.
- **Hosted frontend:** React/TypeScript role-specific navigation, manager dashboard with read-only real status counts, authorized order inbox without manual UUID lookup, revision-specific production-review attention and version history. The owner manually verified the **new** business UI through Render's reviewer gate and a cloud-only manager/sales bearer key after the 2026-10-22 release. This is manual browser UAT, not automated browser E2E. [UAT evidence](https://github.com/butomaya12-wq/handoffguard-ai/issues/6#issuecomment-6338169498); [UI implementation specification](docs/dashboard-issue20.md).
- **Local containers:** standard `docker compose up --build -d` for frontend/backend and persistent synthetic SQLite; local observability Compose is separate and must never share the hosted keys. Do not run `down -v` when local history must survive.
- **Testing and CI:** owner Mac `bash scripts/test-all.sh` on combined feature branch passed **56 backend tests, 17 frontend tests and production build** on 2026-10-22; offline on-call test suite passed **51 tests**. Seven PR-head workflows succeeded before [PR #33](https://github.com/butomaya12-wq/handoffguard-ai/pull/33) squash merge; six push-to-`main` checks succeeded after. A local working-tree test is not a fresh clean-checkout verification; re-check checks on any newer SHA.
- **Cloud release, CI/CD ([Issue #11](https://github.com/butomaya12-wq/handoffguard-ai/issues/11)):** reviewer-cookie-protected same-origin React/FastAPI educational demo on Render Free over HTTPS with managed Neon PostgreSQL and server-validated cloud-only role tokens. Verified automatic Render release on exact `main` SHA [`188957513dbe2678a348a86a9a2492ce0e55340a`](https://github.com/butomaya12-wq/handoffguard-ai/commit/188957513dbe2678a348a86a9a2492ce0e55340a), 2026-10-22. Independent **read-only** Neon check preserved hosted FRAME-01 V1=100/V2=120, one approval and acceptance with matching fingerprints; hosted delivery date is **2026-11-17**, not the local lab's 2026-11-19. The Render status is a point-in-time verification, not a perpetual uptime claim.
- **Hosted telemetry and alerting ([Issues #16](https://github.com/butomaya12-wq/handoffguard-ai/issues/16), [#18](https://github.com/butomaya12-wq/handoffguard-ai/issues/18), [#22](https://github.com/butomaya12-wq/handoffguard-ai/issues/22)):** allowlisted correlated Render JSON business logs and log-derived per-event measures; best-effort in-process user-impact 5xx threshold/Telegram notifier. Owner confirmed a deployed diagnostic Telegram delivery, not an actual hosted outage. No cloud Prometheus/Jaeger, durable metrics store or 24/7 incident response.
- **Local-only observability v2 (merged code, not cloud deployment):** separate Docker Compose synthetic lab, OpenTelemetry trace/log identifiers, Prometheus counters/histogram with exemplars and Jaeger UI; local data retention and localhost scope. See [runbook](docs/observability-v2-lab.md). Never describe this as a remotely hosted instrumentation UI.
- **Local-only on-call agent (merged code, not cloud deployment; [Issue #28](https://github.com/butomaya12-wq/handoffguard-ai/issues/28)):** one independently observed Mac lab outage triggered real OpenAI analysis and one exact Docker backend start after **two explicit startup preauthorizations** and independent verification, followed by healthy Docker and two fresh up-scrapes. It does not run on Render, does not remain active indefinitely and has no general repair privileges. See [local UAT evidence](docs/oncall-autorecover-owner-uat-2026-10-22.md).
- **Still excluded / pending:** full source-ingestion/OCR and runtime AI extraction, production SSO and tenant isolation, automated browser E2E, cloud telemetry UI, unattended cloud on-call repair, course submission and **three peer reviews**. Do not claim production readiness or guarantee external grading for criterion #12. Business workflow and hosted business history must remain unchanged in documentation-only follow-ups.

**Reviewer-ready docs tasks:** [Issue #25](https://github.com/butomaya12-wq/handoffguard-ai/issues/25). [Post-release documentation correction #34](https://github.com/butomaya12-wq/handoffguard-ai/issues/34). **Single source of truth for current course checklists:** [Issue #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6). Historical reports and dated claims above must not be silently presented as fresh checks.

**Safety disclaimer:** Educational synthetic demo, **not production-ready**. Never paste or commit Render/Neon/Telegram/role/reviewer secrets. Never use local demo tokens as public authentication. Do not merge or publish PRs without explicit human approval. Do not alter existing approved Neon V1=100/V2=120 history during submission preparation.
