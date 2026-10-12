# AI coding-agent instructions

**Project:** HandoffGuard AI, AI Dev Tools Zoomcamp 2026 Project 1.

## Invariants that must never be violated

- A client request is **not** an approved order change.
- An AI model never approves, applies, or stops production.
- Pending changes do not modify the current approved order revision.
- Production feasibility is verified by an authenticated production reviewer.
- Only the authenticated single authorized company approver may internally approve.
- Internal approval is not customer acceptance; both are needed to apply.
- Approval refers to an immutable impact-assessment fingerprint. Stale inputs invalidate prior authorization.
- Missing economic inputs are UNKNOWN, not zero; money uses integer kopeks.
- A completed order is not changed/applied in the MVP.
- Maintain provenance and immutable version/audit history; reject unsupported operations.

## Development workflow

1. Read `product-spec.md`, `docs/decision-record.md` and `fixtures/golden-cases.json`.
2. Propose an explicit, scoped change. Do not expand the MVP or invent integrations.
3. Implement one vertical slice at a time; keep frontend/backend calls aligned with `openapi.yaml` once it exists.
4. Add positive and negative automated tests for each business state transition.
5. Run tests and provide actual command output; do not claim a PASS based on code inspection alone.
6. Use fake/synthetic business records in the public repo. Never commit API keys, tokens, real customer documents or credentials.
7. Record AI usage, human review, failures and verification evidence in `docs/` for the course rubric.

## Current state

Repository initialized with design materials. Backend, frontend, tests, Docker, deployment and agent extension pack are upcoming work, not done.
