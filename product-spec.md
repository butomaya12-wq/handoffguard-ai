# HandoffGuard AI — Product Specification v0.3

**Status (2026-10-19):** The human-approved scope (one final internal approver after production review) is **implemented and verified** in the educational FastAPI + React application. Local and CI tests passed; protected Render Free and Neon PostgreSQL are operating with **synthetic data only**. Hosted controls are not production identity or a security certification. [Evidence tracker](https://github.com/butomaya12-wq/handoffguard-ai/issues/6).

## 1. Problem

A customer asks to change an already approved B2B production order. The original order may be queued, partly manufactured, or finished. Applying a request without verified cost, price, schedule and production feasibility may lead to unapproved commitments. HandoffGuard is a **traceable change-impact assessment and approval gate**, not a CRM or ERP replacement.

## 2. MVP users and authority

- **Sales manager:** records client request, validates extracted facts and prepares a proposal; cannot approve.
- **Production reviewer:** records an authenticated production snapshot and feasibility judgment; cannot give final approval.
- **Company approver:** the **single final internal approver**, who may approve/reject an assessment based on a verified production review; cannot override missing or stale assessment.
- **Customer:** accepts modified commercial terms externally. A recorded, verified acceptance of the same quantity, price and date is a separate apply-time gate.
- **AI:** may extract candidates and quote evidence, but cannot calculate authoritative totals, authorize or apply changes.

For a public demo, authentication and authorization must be enforced server-side. Client-supplied role names cannot confer permission.

## 3. MVP functional boundary

One approved order with one SKU and positive integer quantity in pieces. Client may request quantity, unit selling price or delivery date changes. Persist immutable order revisions and an audit trail. Production feasibility comes from a human reviewer, not AI.

Store monetary amounts as **integer kopeks**. Optional estimated unit variable costs and one-time change costs must be verified; missing values are **UNKNOWN**, never zero.

Excluded: real 1C/Bitrix24 writes, manufacturing execution, auto-stop, actual stock/capacity simulation, legal e-signatures, OCR for scans, multi-SKU and production scheduling.

## 4. Three independent state dimensions

1. **Approved order / production:** `NOT_STARTED | IN_PRODUCTION | COMPLETED`. Pending changes never modify or pause the existing approved order.
2. **Change lifecycle:** `DRAFT → ASSESSMENT_REQUIRED → PENDING_APPROVAL → INTERNALLY_APPROVED → APPLIED`. A pending request may be `REJECTED`. Material changes invalidate previous approvals.
3. **Impact readiness:** `READY_FOR_APPROVAL | NEEDS_DATA | CONFLICT`. New requested quantity differing from the baseline is not automatically a conflict.

`READY_FOR_APPROVAL` requires verified commercial inputs, current feasible production assessment and no contradictory authoritative sources. Missing customer acceptance blocks **application**, not the internal impact assessment.

A `COMPLETED` production order cannot have a revision applied in MVP.

## 5. Workflow

1. Create original approved order with source reference and immutable revision 1.
2. Record human production review (stage, completed units, feasibility, note, reviewer, time).
3. Register customer source and proposed change without mutating the approved revision.
4. *(Planned extension, NOT part of running MVP):* AI may extract structured change candidates from a source. In the implemented app, sales enters/verifies proposed terms manually.
5. Assess proposed values using deterministic code, with an immutable assessment fingerprint tied to verified inputs and the production snapshot.
6. Production feasibility `UNKNOWN` or `NOT_FEASIBLE` prevents approval submission; change remains blocked and original work may continue.
7. Authorized approver signs off the exact assessment fingerprint or rejects with an audit record.
8. Record and verify explicit customer acceptance matching the internally approved proposed quantity, unit price and date.
9. Apply creates a new immutable approved revision and handoff record; older revisions remain available.

### Economic calculation

- `old_revenue = old_quantity * old_unit_sales_price_kopeks`
- `new_revenue = requested_quantity * verified_new_unit_sales_price_kopeks`
- `delta_revenue = new_revenue - old_revenue`
- `old_est_variable_cost = old_quantity * old_unit_est_cost_kopeks` **only if known**
- `new_est_variable_cost = requested_quantity * new_unit_est_cost_kopeks + one_time_change_cost_kopeks` **only if every component is known**
- Calculate estimated contribution change only when **all** corresponding inputs are known.
- Costs and contribution are scenario estimates, **not actual realized margin**. Produced units imply exposure risks; they do not prove sunk cost or a financial loss.

## 6. Provenance and audit

**Implemented now:** Record an original approved source reference, the separate change proposal and reason, authenticated production review, company approval decision and its assessment fingerprint, matching customer acceptance evidence, and revision snapshots. Changing commercial inputs or the production snapshot invalidates prior assessment authority. **Planned, not implemented:** comprehensive source type/excerpt ingestion, source SHA-256 storage and an AI extraction pipeline with `PROPOSED`/`HUMAN_VERIFIED` states. These cannot be claimed as working hosted functionality.

## 7. Minimum tests / release gates

- A: increase 100 → 120 before production; valid feasibility; calculation; authorized internal approval; matching customer acceptance required to apply.
- B: 80 of 100 already manufactured; increase to 120; feasibility unknown; report monetary scenario, but `NEEDS_DATA`; no approval/application and original production unchanged.
- C: expedited delivery; missing feasibility/rush cost; no guessed price or deadline; `NEEDS_DATA`.
- Negative authorization: sales user attempting approval returns `403`.
- Immutable revisions, stale-fingerprint invalidation, rejection blocking, no apply to completed order, customer acceptance equality.

Golden cases: [fixtures/golden-cases.json](fixtures/golden-cases.json). These are **expected outcomes**, not evidence that tests have passed.

## 8. Implementation, course requirements and delivery

**Verified implementation (2026-10-19):** full-stack React/FastAPI, persistence (SQLite/Compose locally; Neon PostgreSQL on Render), role-separated human approval workflow, Python/React tests and build, cloud Docker image, five GitHub CI workflows, automatic CI-gated Render deployment and separately tested rollback, allowlisted correlated logs, bounded Telegram 5xx alerting and an owner-received Render-origin diagnostic. Details: [tracker #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6), [live cloud evidence #11](https://github.com/butomaya12-wq/handoffguard-ai/issues/11), [observability #16](https://github.com/butomaya12-wq/handoffguard-ai/issues/16), [alerting #18](https://github.com/butomaya12-wq/handoffguard-ai/issues/18) and [diagnostic #22](https://github.com/butomaya12-wq/handoffguard-ai/issues/22).

**Not implemented:** source-document ingestion endpoint (despite its appearance in the [draft OpenAPI contract](openapi.yaml)), live AI extraction, autonomous on-call responder, production-grade security, persistent external metrics, and automated browser E2E. Cloud credentials stay private and the public URL requires a separately authenticated reviewer session. Demo alerts are best-effort and reset on service restarts. The system is **not production-ready**.

**Submission requirements:** reviewer-readable **English documentation**, a verified final commit, links to evidence, submission via the [cohort platform](https://courses.datatalks.club/ai-dev-tools-2026/) and **three mandatory peer reviews**. An earlier planning record gives **27 October 2026 at 04:00 in the course-account timezone**, but this has **not been independently reverified** on the course platform. Confirm the current deadline, form and peer-review instructions there before submitting.
