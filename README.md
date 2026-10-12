# HandoffGuard AI

**DataTalks.Club AI Dev Tools Zoomcamp 2026 — Project 1**

> **Progress: Backend Gate 01 implemented and locally tested.** This is an educational development slice, **not a complete or deployed product**.

HandoffGuard AI is a B2B manufacturing **change-impact assessment and approval gate**. When a customer requests changed terms on an approved order, the system checks the latest production review and estimated financial impact before an authorized company approver may approve the proposal.

**Critical invariant:** a customer message, AI output, or sales manager request cannot directly modify the approved order or pause existing production.

## Current implementation (Gate 01)

- FastAPI backend with persistent SQLAlchemy tables (SQLite for local/test; PostgreSQL URL supported by SQLAlchemy when a driver is installed).
- Original order, human production reviews, proposed change, deterministic impact assessment, internal approval decision.
- Authenticated role gates: `sales`, `production`, `approver`; role is **never trusted from request JSON**.
- Monetary calculations in **integer kopeks**; missing costs yield null rather than invented zeros.
- Reviews preserve a verified production snapshot. New production information invalidates pending and even previously approved assessments.
- Change proposals cannot mutate the approved order. Approval in Gate 01 is **internal only**; revised order application is **not implemented**.
- 11 locally passing pytest API checks, covering three primary gates, stale assessment and role restrictions.

### Not yet implemented

- Customer acceptance, approved revision application, document/source ingestion, true LLM extraction, integrations with Bitrix24 or 1C.
- Frontend, production authentication/SSO, database migrations, full PostgreSQL integration tests, Docker Compose, cloud deployment, CI **deployment**, agent extension pack, full security review.
- The repository's [OpenAPI contract](openapi.yaml) contains three planned operations not implemented in Gate 01: addSource, recordCustomerAcceptance and applyApprovedChange. Existing route schemas will be hardened in later phases.
- No real business data or ROI is claimed.

## Run / test the backend

See [backend/README.md](backend/README.md). Simplest test commands (Python 3.11+):

```bash
cd backend
python -m pip install -e . pytest httpx
python -m pytest -q
```

Local API documentation: `http://127.0.0.1:8000/docs` after configuring environment tokens and running `uvicorn app.main:app --reload`.

## Product and engineering documents

- [Product specification](product-spec.md)
- [Architecture decisions](docs/decision-record.md)
- [Synthetic golden scenarios](fixtures/golden-cases.json)
- [Gate 01 verification record](docs/gate-01-verification.md)
- [AI-assisted development record](docs/ai-development-workflow.md)
- [Coding agent instructions](AGENTS.md)

## Planned full project stack

React + TypeScript → FastAPI + PostgreSQL → Docker Compose → CI/CD → cloud deployment. The entire stack is not delivered yet.

## Course submission

**Deadline:** 27 October 2026 at 04:00 in the course-account timezone. Submission requires this public repository and a final commit SHA. The course also requires peer reviews.
