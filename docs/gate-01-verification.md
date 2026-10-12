# Gate 01 — local verification evidence (13 October 2026)

## Goal

Prove that a customer's proposed change **never** silently alters an already approved order, financial scenarios use deterministic integer arithmetic with unknowns, and a salesperson cannot approve their own change.

## Execution

Environment: Python 3.11+ runtime with FastAPI, SQLAlchemy, pytest and httpx; each test uses a temporary SQLite DB. Command run from `backend/`:

```
python -m pytest -q
...........                                                              [100%]
11 passed in 0.40s
```

The command output above was captured from **local execution before uploading this release**, not a claim about GitHub Actions or production. See `backend/tests/test_gate01.py` for the test bodies.

## Observed checks

1. Customer change 100 → 120 cannot mutate order revision 1.
2. In-production 80/100, requested 120: revenue delta 3,200,000 kopeks; cost delta 1,900,000; estimated contribution delta 1,300,000; feasibility unknown → `NEEDS_DATA` and approval submission blocked.
3. Sales token cannot authorize → HTTP `403`; server-side role mapping.
4. Approved internal proposal still leaves current approved order unchanged.
5. Newly recorded production review invalidates previous assessment and blocks use of its fingerprint.
6. Expedited date with unknown rush cost remains `NEEDS_DATA` and does not promise a new date.
7. Invalid empty changes and implausible production review rejected.
8. Missing token returns `401`; sales cannot impersonate production.
9. A production snapshot recorded after internal approval revokes current approval status and requires reassessment.
10. A production update cannot roll progress backwards.
11. Generated FastAPI OpenAPI exposes Bearer security scheme and decision operation.

## Scope / limitations

- No actual revised version has yet been applied: customer acceptance and application endpoints are not implemented.
- API contract is a **draft**; its unimplemented operations are explicitly documented.
- Tests run in-process using FastAPI TestClient; no browser, PostgreSQL, Docker or cloud e2e assertion is made.
- No independent CI pass is asserted by this document; see the GitHub Actions status separately.
- No AI model or business customer is involved in these deterministic synthetic tests.
