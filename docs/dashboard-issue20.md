# Business analytics dashboard — Issue #20

**State:** isolated feature PR candidate only. Not deployed to Render, not merged into main, and no production/Neon writes have been made by implementing this feature. Human merge and release authorization are required.

## User value

Make the existing manufacturing-order change workflow observable to a permitted human through a compact **read-only** analytics panel alongside the original approval UI.

## Application layout and one-role session (owner-requested UX revision, PR #27)

The original single scrolling page and three role-token inputs were rejected at owner screenshot review. The draft implementation provides one backend-validated sign-in using `GET /api/v1/me`, which returns **only the validated role**, never the token or actor identity. A role-appropriate left sidebar separates pages; sales and approver enter at the dashboard, production enters at order selection and production review. Sales can create orders/changes, calculate and submit assessments and record customer acceptance; production can record reviews; approver can make decisions and apply only after customer acceptance; all can open permitted order history. All role checks still happen on the server; hiding buttons is not authorization. Dashboard rows can open the corresponding persisted order via the existing authorized API. Token stays in React memory, sign-out clears it.

This is **not production SSO** and intentionally cannot be used to impersonate or choose a role without a valid configured token. The hosted reviewer gate still applies before the app login.

## Verified schema, metrics and filters

The persistent `changes` table supplies `status`, `requested_quantity`, `baseline_revision`, `order_id` and `id`. The `orders` table supplies the currently approved revision. A change **does not have a created_at timestamp**, so any trend/date filter would be fabricated.

All KPI values are aggregate counts of persisted `Change` rows:
- **Total requests:** all rows (including any unrecognized historical statuses).
- **Pending internal approval:** status `PENDING_APPROVAL`.
- **Internally approved, not yet applied:** status `INTERNALLY_APPROVED`.
- **Applied:** status `APPLIED`.
- **Rejected:** status `REJECTED`.
- Additional chart buckets: `DRAFT`, `ASSESSMENT_REQUIRED`. Any unknown statuses counted separately as `unknown_count` and included in total.

These are **workflow counts**, not unique orders, financial return, monthly volume or actual customer impact.

`GET /api/v1/analytics/changes?status=<one-of-six-known-statuses>` returns unfiltered overall counts and only the selected status in the table. The table is capped at **25 rows** ordered by `Change.id` for deterministic reproducibility (UUID order is **not** chronological order). Response fields per item: synthetic change/order IDs, status, requested quantity, baseline revision and current approved order revision. This is not a paging or export API.

## Security and trust

- The endpoint requires valid server-side bearer credentials with role **sales or approver**. Role **production** gets HTTP 403, absent/invalid bearer HTTP 401, unsupported filter HTTP 422.
- On hosted Render, the pre-existing signed reviewer session gate continues to block API requests before bearer authorization.
- The endpoint never returns `Change.reason`, assessment text, customer acceptance or production notes, free-text source fields, actor/reviewer IDs, unit prices, tokens, raw request URLs or exception traces. The SQL only reads data; it neither commits nor changes the core workflow.
- This is **one shared synthetic-demo dataset**. There is **no tenant-scoped authorization**, production SSO, privacy/security guarantee, or permission to deploy with real customer records.
- Empty dataset, forbidden roles, fake/stale credentials and network errors display honest states rather than fake chart data. Switching tokens clears rendered analytics.

## Verification contract

- Backend tests run against disposable local SQLite and assert group-by counts, explicit role denials, filter validation, 25-row cap, absence of sensitive text and unchanged persisted row counts/statuses before and after requests. Existing isolated PostgreSQL CI validates common app behavior, but is **not a separately claimed hosted-dashboard proof**.
- Frontend Vitest: actual mocked API results in KPI/chart/table, server-side filters, empty data, 403 and token change, plus existing workflow UI regression tests.
- Full `bash scripts/test-all.sh`, all GitHub PR workflows and manual UI review are required **before** merge. Owner must separately authorize merge and any consequent automatic Render release.
- Following approved release: verify API/UI via owner-supplied cloud role credentials without revealing secrets, then read-only Neon check of prior V1=100/V2=120, valid approval/acceptance and applied change. Document actual results.
- No source ingestion, new library, extra paid service, data migration or business-process automation is introduced.

## On-call agent: separate follow-up

Optional rubric #12 cannot be scored from Telegram alerts or a static LLM explanation. A real agent must wake from an event and perform a **demonstrably successful, safe repair**. Given these invariants, agent actions on orders, production reviews, approvals, or PostgreSQL history are prohibited. Treat an **isolated, nonbusiness fault** with reversible, allowlisted remediation as an independent design/test exercise under a separate Issue/PR and fresh human authorization. Do not silently introduce VPS, Hermes or broad Render API credentials in this dashboard slice.
