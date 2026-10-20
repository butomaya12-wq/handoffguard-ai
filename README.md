# HandoffGuard AI

**DataTalks.Club AI Dev Tools Zoomcamp 2026 — Project 1**  
**Status verified 2026-10-19:** working educational full-stack demo on Render Free with external Neon PostgreSQL, CI-gated deployment, structured business observability and bounded Telegram alerting. This is **not a production-ready service**.

**[Open the HTTPS educational demo](https://handoffguard-ai-demo.onrender.com)** · [Submission acceptance tracker (#6)](https://github.com/butomaya12-wq/handoffguard-ai/issues/6) · [Product specification](product-spec.md) · [Developer/AI context](AGENTS.md)

> **Reviewer access is required.** The public URL opens a private reviewer login page; it does not grant anonymous access to the business UI. Ask the project owner privately for the reviewer access key and the three **cloud-only synthetic** business-role credentials. No credentials or customer data are stored in this repository. Render Free may take time to wake from inactivity.

## 1. Problem and outcome

An approved manufacturing order can receive a new customer request for quantity, price or delivery changes after production planning has begun. Treating a message or sales proposal as an approved instruction can create unverified commitments and destroy the original agreed terms.

HandoffGuard AI is a **human-controlled change-impact and approval workflow**, not an ERP/CRM replacement or an autonomous production controller:

1. **Sales** creates an original approved order (V1) and later proposes a separate change.
2. **Production** records current progress and feasibility.
3. **Sales** requests a deterministic impact assessment; unknown inputs remain unknown, and stale proposals cannot be approved.
4. A separate, authorized **company approver** approves or rejects the exact assessed proposal.
5. **Sales** records matching customer acceptance of the new terms.
6. Only after both approvals, a permitted apply operation creates **V2** and keeps the V1 history.

**Invariant:** AI-generated text, a customer's request and a pending proposal can never directly rewrite an approved order or stop production. The AI assistant is used to help **develop** the app; it is not an implemented runtime agent that approves business decisions.

## 2. Architecture and scope

```text
Local:   Browser -> Nginx (React/TypeScript) -> FastAPI -> SQLite volume
Hosted:  Browser -> Render HTTPS + reviewer cookie gate
                    -> same-origin React + FastAPI -> Neon PostgreSQL
                    -> allowlisted business-operation logs (Render Logs)
                    -> bounded Telegram notifier for repeated business HTTP 5xx
```

- **Frontend:** React, TypeScript, Vite, typed API calls and explicit review/approval stages. See [frontend/README.md](frontend/README.md).
- **Backend:** FastAPI, Pydantic, SQLAlchemy, server-side role gates, fingerprint-bound approvals and conditional revision updates. Money is represented in integer kopeks; missing cost data never becomes zero. See [backend/README.md](backend/README.md).
- **Persistence:** local Docker Compose uses a named SQLite volume; the hosted demo uses managed Neon PostgreSQL. Order history, approvals and customer acceptance survive releases.
- **Security boundary:** hosted demo has a private reviewer session gate plus three server-validated business-role bearer tokens. It is an **educational shared demo**: no production identity provider, tenant isolation, legal e-signature or real-customer integration.
- **Observability:** structured, redacted, correlated workflow/request UUIDv4 logs and per-event `business_operation_total=1` measurements in Render Logs. These are log-derived signals, **not a persistent metrics database**.
- **Draft integration UI (not deployed):** role-based React screens, business dashboard, pending production inbox and revision-specific review queue from [PR #27](https://github.com/butomaya12-wq/handoffguard-ai/pull/27). The integration [Draft PR #31](https://github.com/butomaya12-wq/handoffguard-ai/pull/31) proposes these features together with local telemetry; the current public Render URL still uses the older UI. See [dashboard specification](docs/dashboard-issue20.md).
- **Optional *local* Observability v2 lab (Draft PR #31, NOT deployed):** real OpenTelemetry request spans and log `otel_trace_id`, Prometheus counter/latency histogram with trace exemplars, and Jaeger UI in a separate Compose project. Visit the lab app at `http://127.0.0.1:8082`, Prometheus `http://127.0.0.1:9090`, Jaeger `http://127.0.0.1:16686`. It uses a different synthetic SQLite volume from the normal local app; it is not enabled on Render. See the [observability lab runbook](docs/observability-v2-lab.md) and [Issue #29](https://github.com/butomaya12-wq/handoffguard-ai/issues/29).
- **Alerting:** a best-effort Telegram notifier for **three HTTP 5xx from the same `createOrder` or `applyApprovedChange` operation within five minutes**, with a 15-minute per-operation cooldown. Controlled 401/403/409/422 outcomes are not outages. In-process counters reset when Render Free restarts/sleeps. The actual backend-to-Telegram diagnostic delivered successfully; **no real incident was simulated on the hosted system**.
- **Not implemented:** autonomous on-call remediation, scanned-message extraction, full source-ingestion API, production SSO, multi-tenant controls, automated browser E2E or a 24/7 monitored service. The [OpenAPI draft](openapi.yaml) includes a **planned** source-ingestion route that is not present in the running application.

## 3. Run locally with one command

**Prerequisites:** Docker Engine/Desktop with the Compose plugin. Provide only synthetic local business-role tokens (never reuse the private hosted credentials).

Create an ignored `.env` in the repository root. Example values for **local development only**:

```dotenv
HANDOFFGUARD_AUTH_TOKENS={"local-sales-only":{"id":"sales-demo","role":"sales"},"local-production-only":{"id":"production-demo","role":"production"},"local-approver-only":{"id":"approver-demo","role":"approver"}}
```

Then from the repository root:

```sh
docker compose up --build -d
```

Open **http://127.0.0.1:8080**. The local Compose app uses a named SQLite volume `gate04_data`. Verify services with `docker compose ps`; stop with `docker compose down`. **Do not** add `-v` to `down` if you want to keep the local database.

For separate FastAPI / Vite development, see [backend setup](backend/README.md) and [frontend setup](frontend/README.md). The local synthetic tokens above are explicitly **unsuitable for public deployment**.

## 4. Tests and CI — reproducible instructions

**Prerequisites for host-based tests:** Bash, Python 3.11+ with venv/pip, Node.js 22/npm. From a fresh checkout, install dependencies once:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e ./backend 'pytest>=8,<10' httpx pyyaml
(cd frontend && npm ci)
```

Run the complete local test/build suite:

```sh
bash scripts/test-all.sh
```

The script fails fast on backend pytest, frontend Vitest or TypeScript/Vite build failures. It does not touch the hosted Neon database. **Historical verified runs:** owner Mac UI branch PR #27: 52 backend + 17 frontend passed, production build PASS; owner Mac telemetry-only PR #30: 46 backend + 9 frontend passed with local `observability` extra installed. **The combined integration PR #31 needs a fresh owner Mac run and exact-head CI proof; do not infer its result from either history.** To run the *additional* real OpenTelemetry in-memory tests without optional-dependency skips, install `backend/.venv/bin/python -m pip install -e './backend[observability]'` first. These are recorded results, not a guarantee of future tests.

Five GitHub Actions workflows validate pull requests: [backend](.github/workflows/backend-ci.yml), [frontend](.github/workflows/frontend-ci.yml), [full stack](.github/workflows/full-stack-ci.yml), [Docker Compose smoke](.github/workflows/docker-ci.yml), and [isolated PostgreSQL integration/cloud image](.github/workflows/postgres-ci.yml). PR #24 passed all five; CI-gated `main` updates automatically deploy to Render. See [deployment and rollback verification (#11)](https://github.com/butomaya12-wq/handoffguard-ai/issues/11). Local Docker + disposable CI records use synthetic data; don't claim a clean-checkout Mac proof unless it was actually run.

## 5. Reviewer walkthrough

1. Open the [live demo](https://handoffguard-ai-demo.onrender.com); authenticate with the privately supplied **reviewer key**.
2. Use the separately supplied **sales**, **production** and **approver** demo-role credentials as prompted in the business UI.
3. Create a synthetic **V1, quantity 100**, record a production feasibility review, propose **120**, assess impact and submit for approval.
4. As approver, approve the exact current assessment; as sales, record matching customer acceptance; apply with the authorized role to obtain **V2, quantity 120**.
5. Verify that both revisions are visible and an invalid/stale or unauthorized operation is blocked. **Use only new synthetic test data**; do not alter the protected historical V1/V2 order in the owner's hosted database without approval.

The owner previously verified a full hosted synthetic V1=100 → approved/accepted V2=120 workflow; read-only Neon checks confirmed its revision history, approval and customer acceptance persisted across multiple Render releases. Browser evidence was **manual**, not automated Playwright/Cypress E2E evidence. The currently protected hosted sample must not be overwritten during review.

## 6. Public task and AI-assisted development evidence

The work is human-led and AI-assisted. **One assistant performed planning, code, testing analysis and security review functions sequentially**; these are roles, not separately deployed independent agents. Human approval was required before merging and deploying.

- [Public project acceptance tracker #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6), with criteria, acceptance and evidence.
- [Agent collaboration specification](docs/agent-team-and-handoffs.md) and scoped [Issue #7](https://github.com/butomaya12-wq/handoffguard-ai/issues/7) / merged [PR #8](https://github.com/butomaya12-wq/handoffguard-ai/pull/8).
- [Testing Issue #9](https://github.com/butomaya12-wq/handoffguard-ai/issues/9), merged [PR #10](https://github.com/butomaya12-wq/handoffguard-ai/pull/10).
- [Deployment/rollback Issue #11](https://github.com/butomaya12-wq/handoffguard-ai/issues/11), including actual Render/Neon verification.
- [Observability Issue #16](https://github.com/butomaya12-wq/handoffguard-ai/issues/16) and merged [PR #17](https://github.com/butomaya12-wq/handoffguard-ai/pull/17).
- [Alerting Issue #18](https://github.com/butomaya12-wq/handoffguard-ai/issues/18), [diagnostic Issue #22](https://github.com/butomaya12-wq/handoffguard-ai/issues/22), merged [PR #19](https://github.com/butomaya12-wq/handoffguard-ai/pull/19), [PR #24](https://github.com/butomaya12-wq/handoffguard-ai/pull/24). Owner-confirmed real diagnostic delivery from Render to Telegram, after which the temporary trigger was switched off.
- [Documentation audit Issue #25](https://github.com/butomaya12-wq/handoffguard-ai/issues/25). [Architecture decisions](docs/decision-record.md), [golden synthetic cases](fixtures/golden-cases.json), [historical AI workflow log](docs/ai-development-workflow.md) and [task-scoped context guide](AGENTS.md).

Historical Gate reports describe evidence **at their original dates**, not the latest release state. Any newer submission release must be checked again.

## 7. Submission status and limits

This is a **course demonstration**, not an incident management, identity, monitoring or factory-control product qualified for production use. Render Free may suspend/restart, Telegram notifications are best effort, and private educational role credentials cannot replace production authentication. The optional **on-call remediation agent** is not implemented.

The [official course project rubric](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md) requires **English documentation and three peer reviews** after submitting. The actual due date, submission form and review workflow must be confirmed on the [cohort platform](https://courses.datatalks.club/ai-dev-tools-2026/). The project's earlier spec recorded **27 October 2026, 04:00 course-account timezone**, but this has **not been independently rechecked**. Do not treat a tentative date as verified or a passing self-check as a peer-review score.
