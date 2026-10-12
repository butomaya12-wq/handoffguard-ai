# HandoffGuard AI

**DataTalks.Club AI Dev Tools Zoomcamp 2026 — Project 1**

> Status: architecture/design milestone. The application is **not implemented or deployed** yet.

HandoffGuard AI is a proposed B2B manufacturing **change-impact and approval gate**. When a customer changes an already approved order, the system evaluates the proposed terms against production status and economic inputs before an authorized person may approve a revised handoff.

**Core invariant:** a client message, an AI extraction, or a sales manager action alone must not modify an approved order or stop production.

## Scope

- One product/SKU per order; quantities are integral pieces.
- Approved order revision and a separate production snapshot.
- Proposed change to quantity, unit price, or delivery date.
- Deterministic revenue/cost delta calculations in integer kopeks; unknown costs remain unknown.
- Production reviewer confirms feasibility; one designated company approver makes the final internal decision.
- Customer acceptance matching the approved revision is required before applying the change.
- Every decision stores provenance and audit history; previous revisions remain immutable.

**Not in MVP:** live 1C/Bitrix24 connectors, factory dispatch, automatic production stoppage, a capacity-optimization engine, scanned PDF OCR, legal e-signatures, and multi-line bills of materials.

## Design documents

- [Product specification](product-spec.md)
- [Architecture decisions](docs/decision-record.md)
- [Golden scenario specifications](fixtures/golden-cases.json)

The first engineering milestone is a **tested backend vertical slice**: create an order → record production review → propose change → assess → authorize → record customer acceptance → apply a new revision. Unapproved changes never modify the baseline.

## Planned stack

React + TypeScript frontend; FastAPI + Python backend; PostgreSQL persistence; OpenAPI contract; pytest and frontend tests; Docker Compose; GitHub Actions; cloud deployment; agent extension pack and security/audit evidence.

The above stack is a plan, **not a statement of implemented features**.

## AI engineering policy

AI may extract information and cite sources. Business values must be verified, arithmetic is deterministic, and internal approval/application requires authenticated human authority. Never put client secrets, credentials, or real customer documents in the public repository.

## Course deadline

Project 1: 27 October 2026 at 04:00 in the course-account timezone. Submission requires a public repository and an exact commit SHA. Peer review is also required for certification.
