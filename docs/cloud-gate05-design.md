# Gate 05: cloud deployment design and risk controls

**State:** Proposal / preflight, not a deployed design. **Task:** [Issue #11](https://github.com/butomaya12-wq/handoffguard-ai/issues/11). **Baseline:** main at `5f77d45` (Testing PR #10 merged). Written as a scoped design/handoff before implementation or resource creation.

## Goal and constraints

Publish a reviewer-accessible HTTPS **educational demo** that persists synthetic order versions and exercises the human-gated V1→V2 workflow. Keep the local SQLite and Docker Compose experience intact. Do not publish test bearer tokens, claim production authentication, change any existing SQLite order or use billable cloud plans without explicit approval.

## Proposed minimal architecture (one web service plus managed DB)

```text
Reviewer browser (HTTPS, demo access gate)
      |
      v
Render Free — one public Docker web service
  - multi-stage Node build creates React dist
  - FastAPI/uvicorn serves dist at / and JSON at /api/v1/*
  - same origin: no permissive CORS or second public backend
  - env-only demo gate and role configuration, no hardcoded credentials
      |
      v  encrypted PostgreSQL connection
Neon Free PostgreSQL (empty, isolated SYNTHETIC demo database)
```

Reasoning: The existing Nginx proxy references the Docker Compose hostname `backend`, which is not a public cloud host. One cloud Docker image serving both API and prebuilt UI avoids split service routing, extra free-instance consumption and broad CORS rules. Local `docker-compose.yml` and its named SQLite volume are unchanged.

**Implementation choice:** a separate cloud ASGI entrypoint can import the current `app.main.app`, mount prebuilt static assets *after* the API routes, and enforce an outer demo-access layer. Do not introduce a catch-all that intercepts `/api/v1/*` or `/health`. Use a platform `PORT` setting and a non-root runtime image. Add tests for an unauthenticated request and the protected demo entrypoint.

**Database choice:** SQLAlchemy already accepts `HANDOFFGUARD_DATABASE_URL`; add a pinned-compatible PostgreSQL driver (psycopg 3), use `postgresql+psycopg://`, and verify connection/SSL, schema creation on **empty** demo DB, JSON/date handling, historical revision persistence, and compare-and-swap on PostgreSQL. Do not infer success from SQLite tests. A DB URL with credentials must remain in Render secrets, not CI logs/docs. The source data in `backend/handoffguard.db` and Docker volume `gate04_data` must never be migrated or mounted.

## Demo access and limitations

The current API uses three **shared environment-configured role tokens**; those do not constitute production identity and must not be reused from local demo. Public deployment must fail closed unless a separate external access gate and new cloud-only secrets are configured. Reviewer access information should be sent via a suitable **private** submission channel, never embedded in GitHub, HTML, Javascript, logs or issue comments. Server-side role checks remain in force after the perimeter access gate.

This is a bounded synthetic demonstration, not a multi-tenant customer system. Existing order read endpoints are not tenant scoped, so reviewers must **not** use personal or confidential data. Do not claim user isolation, production-ready auth or safe unrestricted public API access. Consider rate limits and a reset policy before inviting multiple reviewers. A separate safe demo-session implementation may be needed if the course requires unrestricted public access.

## Implementation/evidence checkpoints

1. **PostgreSQL proof first:** add driver, CI PostgreSQL service and test cases covering create V1, human review, proposed change, fingerprint approval, customer acceptance, apply V2, read after app/client restart, unauthorized 401, forbidden role 403 and a stale/concurrent attempt. CI must use disposable synthetic DB and keep the existing all-tests runner green.
2. **Cloud packaging:** multi-stage Docker build, production ASGI static serving, startup health check and strong env validation. Test same-origin `/api/v1` proxy behavior in a fresh container. Do not change the existing Compose Dockerfiles unless separately reviewed.
3. **Security gate:** implement or configure real access control for the public service without exposing role tokens. Verify unauthorized requests and direct API calls cannot bypass it. Use unique cloud-only credentials and restricted demo data.
4. **PR review:** all CI checks pass, document actual behavior, obtain explicit product-owner merge approval.
5. **Cloud creation (separate permission):** verify current Render/Neon free limits, DB backup/retention and any account or billing requirements. Create resources only with explicit approval; never choose a paid upgrade silently.
6. **Deployed proof:** exercise browser/API HTTPS V1→V2, validate durable revisions across new process/deploy, check Render/Neon logs, define rollback and the CD trigger. Record public URL and actual evidence in [tracker #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6).

## Risks requiring evidence

- Render Free instances sleep and have an ephemeral filesystem; an on-disk SQLite DB there is **not durable**. Render Free Postgres has a limited lifetime: verify latest plan terms before acting.
- External Neon Free Postgres has free-tier limits, project quotas and potential inactivity/suspension; verify current published terms and account status before creating anything.
- Existing `Base.metadata.create_all` is an empty-database initializer, **not** a production migration strategy. The code refuses to invent historical V1 approvals when legacy data lack snapshots.
- Existing frontend imports a convenient **localhost-only development demo token toggle**; never enable that feature in cloud build or reuse the local test tokens.
- Cloud deployment is not the same as a security audit: no SSO, strong per-user roles, tenant isolation, data lifecycle, formal migrations, or production rollback is implemented yet.
- No claim of successful PostgreSQL persistence, public URL or CD until the respective tests and live deployment confirm it.

## Working method

Feature branch `feature/cloud-gate05-issue11` → draft PR → actual CI with Postgres → human approval → merge → separately approved Render/Neon setup. One explicit local terminal action at a time; issue logs record real evidence, never imagined green checks.
