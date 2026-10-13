# Frontend Gate 03 — review and verification log (2026-10-13)

## Context and delegation

- Course context: DataTalks.Club AI Dev Tools Zoomcamp 2026, Module 2 full-stack development and final project rubric.
- Source of truth: `product-spec.md`, `AGENTS.md`, `openapi.yaml`, actual FastAPI routes in `backend/app/main.py`.
- AI implementation task: create a narrowly scoped React + TypeScript interface using a centralized typed API client, synthetic data only and no bypass of server-side approval controls.
- Owner/business rule: new order revisions require production feasibility, internal approval and matching customer acceptance; no LLM may authorize an order.
- Frontend scope: create/read order, history, production review, quantity-change proposal, assessment, internal decision, customer acceptance and application.

## Technical decisions

1. `frontend/src/api.ts` owns every HTTP request and displays server error details including 409 conflicts. JSON never claims actor roles.
2. Bearer tokens are typed into a **local demo-only** panel and held in React state, not localStorage or committed code.
3. Vite development proxy forwards `/api` to `http://127.0.0.1:8000` (no open CORS policy).
4. Monetary amounts pass as integer kopeks. React is a view/orchestration layer; FastAPI remains authoritative.
5. The application deliberately does **not** implement production SSO, a synthetic signed customer document, or a browser-only permission bypass.

## Independent checks and corrections

- First frontend CI attempt: tests failed because component renders were not cleaned between tests; querying the V2 button found two copies.
- Correction: `afterEach(cleanup)` added in `src/App.test.tsx`.
- After correction, GitHub Actions run **38375643572**: 2 test files, **6 tests PASS**; `tsc -b && vite build` PASS.
- Backend GitHub Actions run **38375643559**: SUCCESS (backend change not introduced by this PR).
- The frontend code has **not** yet been manually tested in a browser against a live backend. Avoid claiming end-to-end PASS.

## Blocking tasks before merging or claiming completed full stack

- Generate and commit `frontend/package-lock.json`, switch CI to `npm ci`.
- Browser smoke test identified intermittent 403 on customer acceptance with auto-filled password inputs. Mitigation: user-activated Vite-local role mode now resolves hardcoded synthetic tokens outside password fields. This requires Mac re-test; production RBAC remains enforced by FastAPI.
- Complete actual browser smoke test: create V1, production review, submit approval, record matching customer acceptance, apply V2, verify V1 history.
- **Resolved in PR #3:** GET /api/v1/orders/{order_id}/changes restores persisted assessment and acceptance state. Backend read-only and role-gate test added; frontend UI restore test added. Manual Mac browser recheck remains pending.
- Update docs/screenshots with observed results. Docker, PostgreSQL, cloud deployment and authenticated user management are future gates.

## Learning point

**API client** is a boundary that centralizes `fetch`, authentication headers, endpoint addresses, and HTTP error handling. Each React form only invokes a typed client method. Backend performs the final business-rule checks.
