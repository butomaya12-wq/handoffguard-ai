# Frontend Gate 03 · HandoffGuard AI (educational MVP)

React 19 + TypeScript + Vite. API methods are centralized in `src/api.ts`. Backend FastAPI is the source of truth for role authorization, commercial calculations and revision application.

## Run locally
1. Start FastAPI as documented in `backend/README.md` at http://127.0.0.1:8000 with **synthetic** local demo tokens for roles `sales`, `production`, `approver`.
2. Start frontend:
```sh
cd frontend
npm ci
npm run dev
```
3. Open http://127.0.0.1:5173. Enter **one** synthetic key to sign in; FastAPI validates it at `/api/v1/me` and returns its role. For the local development example, use `demo-sales`, `demo-production`, or `demo-approver` only if those are the configured local keys. Vite proxies `/api` to the local FastAPI server; no CORS changes needed.

## Verify
```sh
npm test
npm run build
```

## Limits
- **New workspace navigation (draft PR #27, not yet deployed):** one verified-role sign-in screen, role-specific left sidebar, dashboard as first page for sales and approver, orders, production (production role), change proposals (sales), approval (approver), approved history. Unavailable role actions are hidden **and** independently blocked by FastAPI. To switch roles, sign out and authenticate again with a different authorized synthetic key. No multiple-token control strip. Dashboard uses only read-only summary and automatically refreshes on entry.
- Credentials stay only in page memory; signing out removes them and clears the selected business record from the visible app. This is an **educational bearer-key sign-in**, not production SSO or an invitation to use real company credentials.
- Requests use only synthetic data. No LLM approval, 1C/CRM connection, e-signature or production identity verification.
- Saved change state (including assessment and matching customer acceptance) is read back from the backend after opening the order. A sessionStorage entry keeps the last demo order ID for this tab only; it does not persist tokens. Multiple saved changes are selectable. No automatic production SSO exists.
- A committed `package-lock.json` is present. CI and Docker builds use reproducible `npm ci`; the UI is shipped both in local Docker Compose (Nginx) and the protected Render Free same-origin cloud image. See [root README](../README.md) and [deployment evidence](https://github.com/butomaya12-wq/handoffguard-ai/issues/11).
