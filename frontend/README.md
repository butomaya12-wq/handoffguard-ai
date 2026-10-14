# Frontend Gate 03 · HandoffGuard AI (educational MVP)

React 19 + TypeScript + Vite. API methods are centralized in `src/api.ts`. Backend FastAPI is the source of truth for role authorization, commercial calculations and revision application.

## Run locally
1. Start FastAPI as documented in `backend/README.md` at http://127.0.0.1:8000 with **synthetic** local demo tokens for roles `sales`, `production`, `approver`.
2. Start frontend:
```sh
cd frontend
npm install
npm run dev
```
3. Open http://127.0.0.1:5173 and enter the matching demo role tokens. Vite proxies `/api` to the local FastAPI server; no CORS changes needed.

## Verify
```sh
npm test
npm run build
```

## Limits
- Credentials stay only in page memory; for local Vite development, a user-activated **local demo role mode** sends the fixed synthetic tokens per endpoint without trusting browser password autofill. It is never enabled for public builds. **Not production login:** never enter real tokens or deploy this multi-role demo login publicly.
- Requests use only synthetic data. No LLM approval, 1C/CRM connection, e-signature or production identity verification.
- Saved change state (including assessment and matching customer acceptance) is read back from the backend after opening the order. A sessionStorage entry keeps the last demo order ID for this tab only; it does not persist tokens. Multiple saved changes are selectable. No automatic production SSO exists.
- There is not yet a committed npm lockfile; CI uses `npm install` until the lockfile is generated and committed. Reproducible `npm ci`, Docker and deployment are later gates.
