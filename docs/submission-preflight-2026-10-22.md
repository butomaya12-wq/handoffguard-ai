# Project 1 submission preflight — 2026-10-22

**Course:** DataTalks.Club AI Dev Tools Zoomcamp 2026, Project 1.
**Public project:** https://github.com/butomaya12-wq/handoffguard-ai
**Official rubric:** https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md
**Submission page:** https://courses.datatalks.club/ai-dev-tools-2026/project/project1

## Deadline and submission form (verified from the public platform on 2026-10-22)

The platform currently shows **2026-10-26 23:00**, explicitly in the viewer's timezone. Reconfirm after logging in because the user's registered timezone may differ.

The form requests a public repository URL, **exact commit SHA**, project time spent (hours), and certificate name; learning-in-public links and FAQ contributions are optional. A project submission alone does not qualify for a certificate: **three peer reviews** are mandatory after submission.

The official project rubric has **12 criteria** with the indicated pass threshold **10 points**; only peer reviewers assign scores. Documentation must be in English.

## Currently verified evidence (do not conflate branches)

- `main` baseline `3de22dcf98cc544d70ca88148af1388c22706900`: GitHub public repo; README/spec/AGENTS, end-to-end full-stack demo, tests/CI/CD, Render HTTPS educational demo with separate protected reviewer access and hosted Neon synthetic V1/V2. Earlier proof is recorded in issue #6 and issue #11. Do not assume the latest unpublished dashboard/telemetry/on-call code is deployed.
- Draft feature stack: #27 business dashboard UI (base main), #30 observability (base main), #31 integrates UI and observability (base #27), #32 on-call agent (base #31). These are **NOT merged** or automatically deployed.
- The current on-call branch head at preflight before this document: `729307a7201b6c007a9879a2f7e316f35cfadba8`, 87 commits ahead of `main`, 40 changed files across the full stacked set. All seven CI workflow runs on this head succeeded.
- Owner Mac on-call tests: **51/51 PASS**. A real owner-run one-shot synthetic lab UAT confirmed two distinct Prometheus down scrapes, one actual OpenAI GPT-5.4 mini triage, a fixed backend start initiated automatically *within the agent process* using prior explicit session authorizations, Docker healthy and two separate fresh up scrapes, and owner screenshot of persistent `FRAME-01` V1=100/V2=120, both 1000 RUB/unit and due 2026-11-19. Details in `docs/oncall-autorecover-owner-uat-2026-10-22.md`.
- **Important scope:** not a production/on-prem 24/7 responder; LLM receives no Docker tools, commands, raw logs, customer information or secrets. All tests and incidents are isolated to the owner's local synthetic Docker Compose lab on port 8082; the hosted Render application has not been changed or tested with this on-call agent.

## Remaining gates before submission

- [x] **Mac working-tree full-stack smoke verified by owner (2026-10-22):** `bash scripts/test-all.sh` finished with `PASS: all checks completed successfully.` Backend pytest: **56 passed, 1 non-failing Starlette TestClient/httpx deprecation warning**, 2.48 s. Frontend Vitest: **17 passed across 3 test files**, 1.25 s. TypeScript + Vite production build: **PASS**, 32 modules transformed, 788 ms. Earlier separate on-call suite: **51/51 PASS**. This does not constitute a fresh clean-checkout verification; that remains optional follow-up if feasible.
- [ ] **Release decision (owner approval required):** choose between the proven hosted `main` as a conservative submission, or carefully integrate the stacked draft branches into `main` with explicit authorization and staged tests. **Do not merge, retarget or deploy without explicit permission.** Never silently expose synthetic role tokens or the local lab API key.
- [ ] If integrating: review accumulated diff, update stale English README and reviewer walkthrough to accurately separate public Render capabilities from local-only optional lab; rerun all CI and check actual provider deployment and data persistence without modifying protected hosted orders.
- [ ] Verify that any included observability signals satisfy the rubric wording for collection/storage/viewable UI; log-derived metrics alone are not automatically equivalent to full real traces+metrics UI.
- [ ] Capture **final `main` commit SHA**, verify public demo access and exact reviewed release SHA, and record a concise English demo/readme with criterion→evidence links.
- [ ] Log in to Project 1 course submission page, confirm **viewer-local deadline**, submit public GitHub URL, exact evaluated commit, factual hours, and certificate name.
- [ ] Complete **three assigned peer reviews** within the separately posted review window. Never assert that they are done before the platform confirms them.

## Review anchors

- https://github.com/butomaya12-wq/handoffguard-ai/issues/6
- https://github.com/butomaya12-wq/handoffguard-ai/issues/28
- https://github.com/butomaya12-wq/handoffguard-ai/pull/27
- https://github.com/butomaya12-wq/handoffguard-ai/pull/31
- https://github.com/butomaya12-wq/handoffguard-ai/pull/32
- https://github.com/butomaya12-wq/handoffguard-ai/blob/feature/oncall-agent-safe-local-design-issue28/docs/oncall-autorecover-owner-uat-2026-10-22.md
