# Frontend Gate 03 — review and verification log (updated 2026-10-14)

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

- First frontend CI attempt failed because component renders were not cleaned between tests; correction: `afterEach(cleanup)` in `src/App.test.tsx`.
- Frontend dependency hardening: Vitest `^3.2.4` → `^5.0.4`, generated and committed `frontend/package-lock.json`, and changed CI from `npm install` to `npm ci`.
- On the developer's Mac (2026-10-14): `npm test` passed **8/8 tests** (2 files); `npm run build` passed; `npm audit` reported **0 vulnerabilities**. The zero-vulnerability result is for the installed dependency tree at the time of that check, not a permanent security guarantee.
- Final commit `40356cf5d2e1d1f4c2c52f3335508ff2f180b075`: GitHub Actions frontend run **38616151162** passed `npm ci --no-audit --no-fund`, `npm test`, and `npm run build`; backend run **38616151154** passed backend API/contract/race-regression tests.
- Browser E2E **manual PASS**, observed on the developer's Mac across 2026-10-13/14 with live React + FastAPI + SQLite, using synthetic data and local demo roles:
  - Created and approved V1 for `FRAME-01`: **100 units** at **1,000 RUB/unit**; initial delivery date 2026-11-12.
  - Production review confirmed; change proposal increased quantity to **120**, with assessed revenue delta **+20,000 RUB** and `READY_FOR_APPROVAL` assessment.
  - Human approver explicitly accepted the internal decision; customer acceptance was recorded; user clicked Apply V2, saw successful completion and history showing both **V1 100** and **V2 120**.
  - After closing both Terminal processes and restarting FastAPI and Vite, reloaded order `fbdd9c49-78b4-43b4-8f1b-a4fd996a8d2f` and confirmed historical V1 100 and current V2 120 still present. This verifies persisted revisions through restart in the local test environment.
- Browser auto-fill caused/was associated with an intermittent sales-role 403 at customer-acceptance time (exact root cause **not proven**). The user-activated Vite-local demo-role mode selects role-correct synthetic tokens independently of password fields; actual server-side role authorization remains enforced. End-to-end success was subsequently observed.
- `GET /api/v1/orders/{order_id}/changes` supports restoring server-persisted change/assessment/acceptance status after browser reload; read-only and role-gate backend test and frontend tests are included.

## Review limits and follow-ups

- Manual browser E2E is evidenced by user-observed UI and screenshots in the working conversation; **no automated browser E2E suite** or checked-in screenshot artifact is claimed.
- Local synthetic role selection is **not production authentication**. Production SSO/authentication, Docker, PostgreSQL, cloud deployment, CI security scanning and operational hardening are future gates.
- `npm ci --no-audit` intentionally skips npm auditing in CI; the developer separately ran `npm audit` locally and observed zero reported vulnerabilities.
- This gate is an educational full-stack vertical slice, not a production-ready release. PR #3 remains Draft pending final review/merge decision.

## Learning point

**API client** is a boundary that centralizes `fetch`, authentication headers, endpoint addresses, and HTTP error handling. Each React form only invokes a typed client method. Backend performs the final business-rule checks.
