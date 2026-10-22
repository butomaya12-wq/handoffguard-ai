# Project 1 submission preflight — updated after 2026-10-22 release

**Course:** DataTalks.Club AI Dev Tools Zoomcamp 2026 — Project 1.  
**Public repository:** https://github.com/butomaya12-wq/handoffguard-ai  
**Hosted educational demo:** https://handoffguard-ai-demo.onrender.com  
**Official rubric:** https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md  
**Submission page:** https://courses.datatalks.club/ai-dev-tools-2026/project/project1  
**Acceptance tracker:** https://github.com/butomaya12-wq/handoffguard-ai/issues/6  
**Documentation correction:** https://github.com/butomaya12-wq/handoffguard-ai/issues/34

## Deadline, form and review obligation

The platform displayed **2026-10-26 23:00 in the viewer's timezone** when inspected on 2026-10-22. The owner must confirm the actual cutoff **after signing in**; do not infer timezone from the code repository or this document.

The form requests the **public repository URL**, **exact evaluated commit SHA**, factual project **hours** and the name for the certificate. Learning-in-public and FAQ contributions are optional. Course documentation must be **in English**. The official rubric has 12 criteria, up to 24 points, with 10 points required to pass; only the course's peer reviewers assign the score. Submission alone does **not** pass: **three peer reviews are required**.

## Verified release: do not confuse hosted and local implementations

- **2026-10-22 owner-authorized release:** consolidated [PR #33](https://github.com/butomaya12-wq/handoffguard-ai/pull/33) was squash-merged to `main` commit [`188957513dbe2678a348a86a9a2492ce0e55340a`](https://github.com/butomaya12-wq/handoffguard-ai/commit/188957513dbe2678a348a86a9a2492ce0e55340a).
- **CI:** all seven PR-head checks succeeded before merging; six push-to-`main` checks succeeded on the final merge commit, as recorded in [Issue #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6#issuecomment-6337696398). These are distinct workflow trigger sets.
- **Render:** automatically deployed exactly that SHA via `new_commit` (deploy `dep-dbctivrbc2fs738rb18g`), provider status **live** completed 2026-10-22T09:38:54Z. No manual deploy requested.
- **Neon durability:** independent before/after **read-only** SQL checks preserved original hosted synthetic FRAME-01 V1=100 and approved/accepted V2=120; both 1,000 RUB/unit and due **2026-11-17**; one applied change, one internal approval and one customer acceptance remained linked.
- **Browser UAT:** owner opened the hosted protected reviewer gate, signed in with cloud-only manager/sales credential, saw one real applied change on the read-only dashboard, opened `FRAME-01 · V2` from the inbox without UUID, and viewed V1/V2 history. The newly approved V2 still truthfully displays `Requires production review`. See [2026-10-22 screenshot-based UAT evidence](https://github.com/butomaya12-wq/handoffguard-ai/issues/6#issuecomment-6338169498). This is **manual** browser proof; no new hosted write cycle or automated browser E2E is asserted.
- **Optional *local-only* observability:** OpenTelemetry, Prometheus UI and Jaeger UI are in merged source code, but run in a **separate localhost Compose lab** with synthetic SQLite and local telemetry volumes, **not on Render**. To inspect, reviewers must run the documented lab locally; cloud Render Logs are a separate, more limited correlated log signal. See [runbook](observability-v2-lab.md).
- **Optional *local-only* on-call remediation:** owner witnessed one genuine isolated Prometheus-down alert → OpenAI triage → fixed `docker compose start backend` (following two separate explicit startup preauthorizations) → independent Docker health and two distinct up scrapes, with local synthetic V1/V2 history unchanged. See [UAT](oncall-autorecover-owner-uat-2026-10-22.md) and [Issue #28](https://github.com/butomaya12-wq/handoffguard-ai/issues/28). This is **not** a cloud, 24/7 or general-purpose on-call responder; criterion 12 credit is up to external peer reviewers.
- **Owner Mac tests on combined branch 2026-10-22:** 56 backend pytest PASS, 17 frontend Vitest PASS, TypeScript/Vite build PASS, separate offline on-call suite 51 PASS. One non-failing Starlette/httpx deprecation warning. This is **not** a clean-checkout verification of a later documentation commit.

Historical pre-release documents, draft PR descriptions and comments remain valid evidence of what was known **at those dates**, not current deployment claims. The final evaluated `main` SHA may change after any later documentation-only merge; the owner must record the SHA actually submitted.

## Final submission gates

- [x] Original release code merged with owner authorization; GitHub, CI, Render and Neon verified at `1889575`.
- [x] New hosted dashboard/order inbox and V1/V2 history manually verified by owner in browser.
- [ ] Review and merge English documentation update from [Issue #34](https://github.com/butomaya12-wq/handoffguard-ai/issues/34) **only with separate owner approval**. `main` uses CI-gated automatic Render deployment; a documentation-only merge may still trigger it.
- [ ] Confirm current SHA and actual CI runs for **the exact commit to be submitted**. If another Render deployment occurs, verify its status and avoid unapproved data mutation.
- [ ] Optional: reproducibility test from a fresh clean checkout with documented synthetic env values; do not re-label working-tree tests as this evidence.
- [ ] Provide reviewer-specific English instructions for hosted access; share synthetic **cloud reviewer and role keys only through a private authorized channel**, not repository text, public issue, screenshots or submission forms.
- [ ] Sign in to course platform; confirm local deadline and submit repository URL, evaluated final SHA, actual hours and certificate name.
- [ ] Complete **three peer reviews** in the platform's specified review window. Do not assert completion before the platform confirms it.

## Required limitations to retain

Educational demo only: no production SSO, multi-tenant security, signed legal acceptance, customer ingestion/OCR pipeline, automated browser E2E, hosted Prometheus/Jaeger, unattended cloud recovery, production SLA or general-purpose factory automation. Hosted sample order V1/V2 and its approvals must remain unchanged during submission preparation.
