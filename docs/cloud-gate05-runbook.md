# Gate 05 — reviewer demo cloud deployment runbook

**Historical planning/runbook snapshot (before first hosted release, 2026-10-18).** The original steps and unverified-at-the-time statements below describe the *predeployment* state; do **not** use them as the present project status. The application was subsequently deployed to [Render Free](https://handoffguard-ai-demo.onrender.com) backed by Neon PostgreSQL, with actual CI-gated deployment/rollback and preserved approvals verified in [Issue #11](https://github.com/butomaya12-wq/handoffguard-ai/issues/11). By **2026-10-19**, [Issue #18](https://github.com/butomaya12-wq/handoffguard-ai/issues/18) and [Issue #22](https://github.com/butomaya12-wq/handoffguard-ai/issues/22) recorded completed alerting tests and owner-received private Render-origin Telegram diagnostic; the temporary test flag was switched off. The current overview is [README](../README.md). **Never copy any secrets into issues, chat, screenshots or GitHub.**

## Selected educational architecture

- A **single Docker web service** (candidate Render Free, subject to account and plan confirmation) built from repository root using `Dockerfile.cloud`. The Docker image serves the production React bundle and the FastAPI API on the **same origin** using `app.cloud:create_cloud_app`. Render provides HTTPS termination. No extra public backend or permissive CORS is required.
- An **isolated external managed PostgreSQL database** (candidate Neon Free). New and empty, containing only synthetic review data. Do not upload existing local SQLite data or customer information.
- A password-protected **reviewer access perimeter** plus three server-validated **synthetic business role tokens**. These are different things: the reviewer session cookie controls entry to the demo; sales, production and approver bearer tokens retain their respective API authorization boundaries. This is NOT production SSO, tenant isolation or end-user identity.

The original local `docker-compose.yml`, backend SQLite default and `gate04_data` Docker volume continue to work independently.

## Evidence available now (isolated GitHub CI, not hosted deployment)

- `bash scripts/test-all.sh`: existing backend API tests, frontend tests and production build.
- [PostgreSQL/cloud CI](https://github.com/butomaya12-wq/handoffguard-ai/actions/runs/39066388687): **5 passing integration/security tests** (2 non-fatal warnings), including real PostgreSQL V1→V2 approvals/persistence, denied role actions, protected demo entry, signed Secure HttpOnly SameSite=Lax session cookie, rejected forged cookie, login throttling, and production startup requiring a PostgreSQL URL and strong reviewer secrets.
- The same run built `Dockerfile.cloud`, started the compiled image against the **ephemeral GitHub PostgreSQL service**, verified the outer gate and role auth, created a synthetic order and found it again **after restarting the cloud Docker container**. Read the workflow logs for exact proof.
- All existing Backend, Frontend, Full-stack and local Docker Compose CI checks remain passing.
- **Not yet proven:** Render routing, TLS termination, Neon connection/SSL mode, longevity/retention of Neon Free database, cloud browser user journey, real cloud redeploy, automatic deployment, rollback and public URL.

## Environment settings (configure as managed secrets, not repository files)

| Name | Purpose |
|---|---|
| `HANDOFFGUARD_DATABASE_URL` | External Postgres URL in SQLAlchemy format `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`. Copy safely from provider and adapt scheme; verify provider TLS settings. Do not use `sqlite:` in cloud. |
| `HANDOFFGUARD_DEMO_ACCESS_KEY` | Strong random reviewer passphrase/key (at least 32 characters), to distribute **privately** only. |
| `HANDOFFGUARD_DEMO_COOKIE_SECRET` | Distinct strong random signing secret (at least 32 characters), never distribute to reviewers. Rotating it invalidates all existing reviewer cookies. |
| `HANDOFFGUARD_AUTH_TOKENS` | JSON mapping of **three distinct long random bearer tokens** to objects with role `sales`, `production`, `approver` and synthetic actor `id`; generated afresh for cloud. Share tokens only via a private reviewer channel, never in public GitHub or the React JS bundle. |
| `PORT` | Render-supplied inbound port; image defaults to 10000 if missing. |

The cloud factory blocks startup for missing/malformed configuration, SQLite cloud URLs, a missing compiled React build, duplicate/missing roles, short demo secrets and known published/test token prefixes. It does **not** perform a comprehensive credential or penetration audit. The local demo token shortcut in React is disabled in production Vite builds.

## Proposed deployment procedure — requires a separate human decision

1. Confirm the Render/Neon account and the exact **free-tier** terms (sleep, quotas, retention, credits and any credit card/billing prompt). Never select a paid plan or add a payment method without the owner's explicit decision.
2. In Neon, create an isolated empty demo PostgreSQL database. Use a dedicated strong credential with limited rights. Confirm TLS is required. Never migrate or mount existing local DB files.
3. In Render, create **one Docker web service** from the reviewed GitHub `main` revision, root build context, `Dockerfile.cloud`, free plan only if available. Configure secrets directly via its secure dashboard; set health-check path `/health` and verify the provider port is passed. Start with reviewed/manual deployment; enable auto deploy for the development demo only after first live verification.
4. Before sending the URL to reviewers: verify `/health` is reachable, `/` redirects to `/demo/login` without a reviewer cookie, direct `/api/v1/*` rejects unauthenticated traffic even if a role bearer token is supplied, and the login sets Secure/HttpOnly/SameSite cookie over HTTPS.
5. Privately share demo access key and the three cloud-only role tokens. Verify browser V1→production review→assessment→internal approval→matching customer acceptance→V2; verify stale approvals and wrong roles are rejected.
6. Verify durability after a **new Render deployment**, not only a process restart, and confirm no local SQLite/Compose volume was touched. Save sanitized test output and screenshot evidence (without tokens, URLs with auth secrets or real data).
7. Only after live proof, configure development auto-deploy from reviewed `main` commits. Demonstrate the webhook trigger and a **reversible** rollback to an earlier image/commit, preserving managed PostgreSQL state; document actual steps and outcome.
8. Update project README, issue #11 and [submission tracker #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6) with the verified public HTTPS URL, CI links, data-retention and access limitations. Never claim production readiness.

## Explicit safety limits and operational concerns

- **Synthetic information only.** There is no tenant/user isolation. Any reviewer with access and role tokens can potentially reach synthetic records known to that shared environment. There is no secure production identity, password-recovery, activity quota or account audit. Do not use real factory/customer data.
- Login attempts are limited **per process and source address**, not globally. In-memory counters reset on deployment; reverse-proxy addressing may reduce accuracy. A stolen reviewer cookie remains valid until expiry (currently 2 hours) or signing-secret rotation; logout removes the browser cookie but does not centrally revoke copied cookies.
- Existing `Base.metadata.create_all` initializes empty tables but is **not a schema migration system**. Do not point the app to an existing unknown database, run destructive migrations or fabricate historical approvals. Snapshot consistency and concurrency must be verified before increasing traffic.
- Free-tier web services may sleep; hosted free database storage/expiration and backup options may change. Confirm provider retention and a clear reset/recovery plan before relying on external demo data.
- `/health` is application liveness, **not** PostgreSQL readiness. Treat operational validation as a separate task. Logs may contain request paths and metadata; never print full Postgres URLs, bearer tokens or reviewer access keys.
- No public demo or CD evidence exists until a live service is actually reached and tested.
