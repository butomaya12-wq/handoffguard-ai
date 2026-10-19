# Gate 07 — short-lived startup test of outbound Telegram delivery (Issue #21)

**Status:** proposal only on a separate feature branch. **Not merged, not deployed, not tested on Render.** The owner authorized PR preparation only. [Gate 07 alerting Issue #18](https://github.com/butomaya12-wq/handoffguard-ai/issues/18) remains open until genuinely observed hosted delivery; [submission tracker #6](https://github.com/butomaya12-wq/handoffguard-ai/issues/6) is authoritative.

## Purpose and constraints

The existing real alert threshold is already released: only three actual HTTP 5xx for the same operation (`createOrder` / `applyApprovedChange`) within five minutes cause one rate-limited alert. Never trigger synthetic 5xx in the live system merely to test delivery.

This **separate TEST** verifies the actual Render FastAPI process can make an outbound Bot API request using the **existing** Telegram credentials, without touching orders, changes, approvals, Neon state, role authorization or public routes.

- Disabled by default: startup checks the optional env var `HANDOFFGUARD_ALERT_TEST_UNTIL_UTC` only **after the existing database startup/integrity check passes**.
- Accept **only** `YYYY-MM-DDTHH:MM:SSZ`, a valid timestamp strictly in the next **1–300 seconds** at the time of startup. Expired, malformed, offset, local-time and far-future values do nothing.
- At most **one test attempt per process start**; it **can repeat** if Render restarts the process multiple times before the 5-minute deadline. Remove the variable immediately after verification. Once the deadline passes, the flag is inert even if forgotten.
- Uses precisely the **same HTTPS `sendMessage` request transport** as business 5xx alerts, with a three-second network timeout; task runs asynchronously so failed Telegram delivery cannot block application startup or modify business responses.
- Message explicitly says **`TEST - NOT AN INCIDENT`**, includes generic demo name, startup UTC time, and no user/order/customer/secret data.
- Structured log events: `alert_test_sent` on Telegram API acknowledgement; `alert_test_failed` or `alert_test_suppressed` otherwise. None of these is a real `alert_sent` or proof of a genuine business incident. Never log raw transport errors because the token is in the request URL.
- No new dependencies, paid plans, public endpoints, scheduled jobs, credentials, database migrations, writes, or automatic incident remediation.

## Tests before any release

1. GitHub's five PR workflows must all pass and the owner runs `bash scripts/test-all.sh` locally.
2. The synthetic SQLite/FastAPI lifespan test proves one **mocked** diagnostic send and zero persisted orders/changes/approvals; other tests cover expiry/malformed/far-future gate, dedup, reused request payload, missing configuration, and redacted transport failures. Automated test transport is **stubbed**; no CI Telegram requests.
3. Keep the PR draft pending explicit owner approval to merge. Because `main` uses CI-gated automatic deployment, merge is also potential deployment approval and must not be inferred from PR creation.

## Future manual proof — requires fresh owner approval first

After the owner **separately** approves merge/deploy and confirms the app is Live on the exact new SHA:

1. Set only `HANDOFFGUARD_ALERT_TEST_UNTIL_UTC` to a **UTC value three minutes in the future** in the existing Render service Environment. **Saving an environment variable can trigger a service redeploy**; obtain explicit owner consent for that action. Never change/copy/render the Telegram token or chat ID.
2. One new application startup while the timestamp is within the 300-second window can dispatch the safe TEST message. No HTTP requests or artificial 5xx are needed.
3. Read **sanitized** Render logs for `event=alert_test_sent` with `operation=channelDiagnostic`, and ask the owner to verify the corresponding TEST message **actually appears** in their private Telegram chat. A transport acknowledgement alone is not enough.
4. Remove the test-until environment variable after confirming the result, even if delivery failed. The removal can cause another deploy; do not modify other settings.
5. Independently query Neon **read-only** and confirm historical V1=100, approved V2=120, one approval and acceptance still match. Record the exact deploy SHA/event, redacted log evidence and owner-confirmed delivery in Issue #18 and tracker #6.

## Interpretation and limitations

A received TEST from Render **proves hosted outbound notification wiring**, while deterministic isolated tests prove the threshold logic. Neither proves 24/7 monitoring, that a real 5xx occurred, real-user harm, delivery under all network conditions, durable counter state or production on-call suitability. The Render Free process can sleep/reset; delivery remains best effort.
