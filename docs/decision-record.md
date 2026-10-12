# Architecture decision record

## ADR-001 — Proposed change is not itself a conflict
**Accepted.** 100 approved units and a customer request for 120 units create a change request, not conflicting authoritative records. Contradictory approved baseline sources may produce `CONFLICT`.

## ADR-002 — Pending request does not stop manufacturing
**Accepted.** Blocking application of new terms is not equivalent to issuing a stop-work instruction. The existing approved revision remains active until separately changed.

## ADR-003 — Human approval and external acceptance are separate
**Accepted.** A production employee records feasibility. The single authorized company approver confirms or rejects the current assessment. Explicit matching customer acceptance is recorded separately before applying a revised order. This demo does not implement legal electronic signatures.

## ADR-004 — No invented financial data
**Accepted as MVP design.** Integer kopeks, verified prices, explicit unknowns; deterministic math. Existing completed units do not automatically establish incurred or unrecoverable cost.

## ADR-005 — Narrow educational scope
**Accepted as plan.** Single-SKU order, synthetic data, backend/frontend, version history; no live factory execution, ERP/CRM writes, OCR for scans or automatic negotiation.

## ADR-006 — One final internal approver
**Approved by product owner 2026-10-13.** Sales and production cannot self-authorize; server-side credentials define roles. Approval is bound to the exact assessed snapshot/fingerprint. Stale feasibility or altered terms make old assessment invalid. No apply without matching customer acceptance.

### Minimum security/invariant tests
1. Sales employee approval attempt → `403`.
2. Unknown/stale production review → cannot submit for approval.
3. Valid reviewer + approver → internal approval only.
4. No matching customer acceptance → cannot apply.
5. Changed proposal or snapshot → invalidates prior approval.
6. Pending change → original production status/revision preserved.
