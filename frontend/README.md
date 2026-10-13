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
- Credentials stay only in page memory; demo shows role switching to test backend RBAC. **Not production login:** never enter real tokens or deploy this multi-role demo login publicly.
- Requests use only synthetic data. No LLM approval, 1C/CRM connection, e-signature or production identity verification.
- This initial vertical slice uses one active order and one active change; reloading loses the current assessment fingerprint (backend keeps order and revision records). Resuming an in-progress change needs new read-only API endpoints.
- There is not yet a committed npm lockfile; CI uses `npm install` until the lockfile is generated and committed. Reproducible `npm ci`, Docker and deployment are later gates.
