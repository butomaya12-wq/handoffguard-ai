# Gate 07 follow-up — opt-in Telegram diagnostic (Issue #22)

**State:** proposed in an isolated draft PR. Not merged, not deployed, no Render setting changes approved.

## Why this exists

Project 1's rubric #11 requires honest evidence that the *deployed backend* can deliver a harmless Telegram message. A direct Mac-to-Telegram test passed but does not prove Render-origin egress. Generating three production HTTP 5xx would be unsafe and misleading. This opt-in backend diagnostic exercises the same HTTPS Bot API transport without triggering any business operation or writing to Neon.

## Design and safety properties

- The **only** trigger is an exact value of a private Render environment setting: `HANDOFFGUARD_ALERT_DIAGNOSTIC_ON_START=SEND_ON_NEXT_START`. It is **not** enabled by default. No new public or reviewer-accessible API route.
- It runs during FastAPI lifespan startup, after read-only database migration checks, and **only** when `app.state.cloud_mode` has been set by the protected `create_cloud_app` factory. Ordinary `create_app` / Compose is inert even when a matching flag exists.
- Uses existing `HANDOFFGUARD_ALERT_TELEGRAM_BOT_TOKEN` and `HANDOFFGUARD_ALERT_TELEGRAM_CHAT_ID` saved securely in Render. **Do not reveal, log, paste, or commit either value.**
- Sends a fixed message: **DIAGNOSTIC TEST**, “Backend-to-Telegram delivery test”, **“No HTTP 5xx triggered. No orders modified. Not a real incident.”** No user/order/actor IDs, chat ID, URLs, token, traces, DB state or exception text.
- Uses exactly the same `AlertMonitor._send_text` HTTPS code used by real alerts. Logs the fixed `diagnostic_sent` on Telegram `ok:true`, `diagnostic_delivery_failed` on error, or `diagnostic_suppressed` for missing/invalid credentials; exceptions are not emitted. If delivery fails, application startup continues.
- **One attempt per opted-in process startup, NOT globally exactly-once.** Render Free may sleep, redeploy or restart. Repeated starts while the flag is set can send duplicates. This must not be described as a reliable one-time task.

## Operator runbook — REQUIRES ANOTHER EXPLICIT OWNER APPROVAL

Do not execute the following steps before the owner approves the draft PR and release.

1. Confirm PR CI is green; run `bash scripts/test-all.sh` locally; approve the separate PR merge/deploy. Verify Render has the release's exact commit `Live`. **Without the flag**, there should be no diagnostic message.
2. With separate owner approval to run the diagnostic, add only the env variable `HANDOFFGUARD_ALERT_DIAGNOSTIC_ON_START` = `SEND_ON_NEXT_START` in Render Environment. Saving it may trigger a redeploy/restart. Do **not** edit existing secrets, database URL, service plan, or reviewer/role tokens. Never put a secret into a screenshot.
3. After the deployment starts, look for one innocuous message with header **HandoffGuard AI | DIAGNOSTIC TEST** in the owner's private Telegram chat; record timestamp and screenshot with sensitive details hidden. Independently check Render Logs for `diagnostic_sent` and `operation=diagnostic`; do not claim delivered on logs alone without receiving the message.
4. **Immediately remove** `HANDOFFGUARD_ALERT_DIAGNOSTIC_ON_START` from Render and save. This may start another deployment. Verify service back to `Live`; keep real alert credentials intact. This minimizes, but does not absolutely prevent, repeated test messages if Render restarts before removal.
5. Verify Neon persisted order V1=100/V2=120, approvals and acceptance unchanged using **read-only SQL**, and record the exact commit/deploy and safe evidence in [Issue #18](../issues/18), [Issue #22](../issues/22), and [tracker #6](../issues/6). Only then consider criterion #11 complete; keep the in-process Free limits explicit.

**Not an incident or user-impact simulation.** This proves Render-origin channel delivery, not that genuine production incidents happened or that alerts are reliable 24/7. No new paid resources, worker, cron, public endpoint or database changes.
