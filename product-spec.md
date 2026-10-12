# HandoffGuard AI — Product Specification v0.3

**Status:** Product owner approved one final internal approver after a separate production review on 2026-10-13. Engineering design remains provisional until tested. All data in the MVP is synthetic.

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
4. Extract structured change candidates if AI is enabled; sales manager verifies all proposed terms.
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

Keep source ID, source type, exact excerpt, timestamp and SHA-256; extraction status `PROPOSED` or `HUMAN_VERIFIED`; human actor, decision and reason; approved order revision; and assessment fingerprint. Changing the proposed terms or production snapshot after assessment invalidates its prior sign-off.

## 7. Minimum tests / release gates

- A: increase 100 → 120 before production; valid feasibility; calculation; authorized internal approval; matching customer acceptance required to apply.
- B: 80 of 100 already manufactured; increase to 120; feasibility unknown; report monetary scenario, but `NEEDS_DATA`; no approval/application and original production unchanged.
- C: expedited delivery; missing feasibility/rush cost; no guessed price or deadline; `NEEDS_DATA`.
- Negative authorization: sales user attempting approval returns `403`.
- Immutable revisions, stale-fingerprint invalidation, rejection blocking, no apply to completed order, customer acceptance equality.

Golden cases: [fixtures/golden-cases.json](fixtures/golden-cases.json). These are **expected outcomes**, not evidence that tests have passed.

## 8. Delivery / course requirements

Implement functional frontend, documented OpenAPI-backed backend, persistence, reproducible Docker Compose, integration tests, cloud deployment, CI/CD, agent extension pack, security/audit records, and AI workflow log.

Deadline 27 October 2026 at 04:00 (course-account timezone). Actual scored project will be a specific final commit SHA. Peer reviews are required.
