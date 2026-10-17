# Development agent roles, context and handoffs

**HandoffGuard AI — DataTalks.Club AI Dev Tools Zoomcamp 2026, Project 1**  
**Status:** documented collaboration process as of 2026-10-17; tracked by [Issue #7](https://github.com/butomaya12-wq/handoffguard-ai/issues/7) and [submission tracker #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6).

## Important distinction: roles are not independently running agents

Development is **human-led, AI-assisted engineering**. A human product owner works with an AI coding assistant which performs multiple *functional review roles* in sequence. The planning, implementation, test-analysis and security-review functions below are **responsibilities within this workflow**, not proof of separately deployed autonomous agents, parallel orchestration, or independent reviewers. Historical evidence and actual CI runs are distinguished from plans.

The development roles below must never be confused with the **application's business roles** (sales, production reviewer, authorized company approver). An AI development assistant cannot make a production decision or authorize the application of a changed order.

## Responsibilities and handoff contract

| Function / responsibility | Actor | Inputs | Outputs and handoff | Authority |
| --- | --- | --- | --- | --- |
| Product owner and final reviewer | Human | Business problem, scope, acceptance criteria, browser observations | Approved business constraints, feedback, explicit approval or rejection of changes | Owns scope, business decisions, and merge permission |
| Specification and planning | AI assistant, functional role | Issue, `product-spec.md`, `AGENTS.md`, decisions | Narrow change plan, risks, acceptance tests, proposed evidence | No business sign-off or unattended merge |
| Implementation | AI assistant, functional role, under human direction | Approved scoped plan, `openapi.yaml`, backend/frontend contracts | Changed code and tests on a feature branch, proposed PR | Cannot bypass invariants; cannot claim tests passed before execution |
| Verification and debugging | AI assistant interpreting **real tool output**, plus automated CI | Test commands, CI runs, logs, manual feedback | Reproducible results, corrections, documented limitations | A PASS requires executed evidence; human checks business behavior |
| Security and release audit | AI assistant, functional review role; human authorizes release | Diffs, authorization rules, Docker/configuration, tests, secret boundaries | Explicit risks, negative tests, release/rollback checklist, blockers | Advises; does not independently authorize public exposure or production deployment |
| Documentation and submission evidence | AI assistant, functional role, human checks accuracy | Issues, merged PRs, CLI/CI evidence, historical reports | English README/docs, links to tasks and tested commits | May document evidence; must not invent autonomous runs or completed features |

The same AI assistant may fulfil several rows sequentially; this is a **role-based workflow**, not six simultaneous AI agents. The human must approve substantive business decisions and PR merges.

## Work process (applies from Issue #7 onward)

1. **Track the task before writing code:** open a public GitHub Issue with scope, acceptance criteria, security constraints and evidence required. Link it from [submission tracker #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6).
2. **Load minimal relevant context:** always read `AGENTS.md` and `product-spec.md`; then read task issue, architecture decisions, golden cases, API contracts and the appropriate implementation/test files. Do not treat old verification reports as the current implementation state.
3. **Specify and review the plan:** AI describes a small, testable change and the human checks business meaning or approves risky scope changes.
4. **Implement in an isolated branch:** adjust code/docs and positive/negative tests without altering the protected approval workflow or using real customer data.
5. **Verify and correct:** run tests, inspect failures, fix and rerun. Record actual local/CI status with commit and workflow links. A GitHub workflow validates its own scope; backend/frontend green checks do not imply deployed production availability.
6. **Human acceptance:** product owner checks user-visible behavior and confirms safety/acceptance criteria. Only merge with explicit permission after relevant CI succeeds.
7. **Handoff:** update the task issue with PR, evidence, unresolved limitations, and review decision; update tracker #6 when completed. Next task starts from these documents rather than reconstructed assumptions.

### Context selection by task

| Task type | Read first (in addition to `AGENTS.md` and `product-spec.md`) |
| --- | --- |
| Business approval logic | `docs/decision-record.md`, `fixtures/golden-cases.json`, `backend/app/main.py`, `backend/tests/` |
| API contract | `openapi.yaml`, `backend/app/schemas.py`, `backend/app/main.py`, `frontend/src/api.ts` |
| UI/workflow | `frontend/README.md`, `frontend/src/App.tsx`, `frontend/src/api.ts`, `docs/frontend-gate03-verification.md` |
| Docker / local run | `docker-compose.yml`, Dockerfiles, Nginx config, `.github/workflows/docker-ci.yml` |
| Cloud deployment / authentication | `backend/README.md`, `docker-compose.yml`, `backend/app/main.py`, `frontend/src/api.ts`, task's security acceptance criteria |
| AI audit / submission | `docs/ai-development-workflow.md`, `docs/frontend-gate03-verification.md`, current Issues, merged PRs and verified GitHub Actions |

## Evidence from real completed gates (predates the public tracker)

### Gate 03 — Frontend and end-to-end order revisions

- [PR #3](https://github.com/butomaya12-wq/handoffguard-ai/pull/3) added the React/TypeScript UI with a centralized bearer-token API client and frontend tests.
- The human verified a **manual** V1 quantity 100 → V2 quantity 120 journey with production assessment, explicit authorized internal decision and matching customer acceptance; V1/V2 history persisted after restarting local processes. See [Gate 03 verification report](frontend-gate03-verification.md).
- A frontend testing failure led to a cleanup correction and CI rerun. This is a documented feedback/verification cycle, **not** evidence of an autonomous testing agent.

### Gate 04 — Docker Compose and CI verification

- [PR #5](https://github.com/butomaya12-wq/handoffguard-ai/pull/5), merged as commit [`703936d`](https://github.com/butomaya12-wq/handoffguard-ai/commit/703936d66b85c956b5c7904f8dedc8ed08ca9410), added backend/frontend Docker images, Nginx reverse proxy, named SQLite volume and Docker CI.
- The human ran local Compose and browser/API checks, including reading a synthetic order after restart.
- [Docker CI run 39047520377](https://github.com/butomaya12-wq/handoffguard-ai/actions/runs/39047520377) built both images, verified unauthenticated 401, authenticated order creation 201, and SQLite persistence after stopping/recreating containers. Backend and frontend checks also passed for PR #5.
- Gates 01–04 were implemented **before** Issues #6 and #7 existed; do **not** claim that those historical tasks were driven by the newly created issue tracker.

## Release and honesty constraints

- An AI assistant never approves/applies a manufacturing change, stops production, manufactures acceptance evidence, or overrides the human approver.
- Approval remains a fingerprint-bound server-side gate; customer acceptance is a separate explicit gate. Missing costs stay unknown, not zero.
- Development examples and public documentation use **synthetic data only**. Never commit `.env`, passwords, API keys, real customer records or credentials.
- Local demo-role bearer tokens are **not production-grade identity management**. No public deployment without an explicitly reviewed access plan.
- Do not represent manual browser checks as automated E2E tests. Do not claim PostgreSQL, monitoring, alerting, rollback, public deployment or an on-call responder agent before implementation and evidence.
- The course's on-call responder agent is a **separate future application/operational requirement**; this development role specification does not fulfil it.

## Current handoff (2026-10-17)

- Backend Gate 02, Frontend Gate 03 and Docker Gate 04 are merged into `main`. Docker Gate 04 has all three CI checks passing.
- [Issue #7](https://github.com/butomaya12-wq/handoffguard-ai/issues/7) records the **first tracked documentation change under this new process**.
- Gate 05 cloud deployment is not yet implemented. Testing consolidation, telemetry, alerting, on-call automation, full security review and peer reviews remain tracked as pending.
