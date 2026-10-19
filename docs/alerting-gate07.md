# Gate 07 — bounded demo alerting (Issue #18)

**Status (2026-10-18):** feature branch `feature/alerting-issue18`, NOT merged, NOT deployed, Telegram delivery NOT verified. Issue #18 owns acceptance criteria; tracker #6 must remain incomplete until real evidence exists.

## Scope

A minimal **in-process, best-effort** threshold for the **existing** HandoffGuard demo. No new worker, SaaS, billing plan, database migration, customer data, auth changes or alert management API.

- Only **POST business operations** `createOrder` and `applyApprovedChange` are watched through `observe_business_operation` (after FastAPI has matched the route).
- Only HTTP **500–599** counts, including safe synthetic HTTP 503 in isolated tests. 401/403/409/422 are normal controlled refusals, not alerts.
- **Three failures of the same operation within five minutes** create an alert; at most one alert of that operation per **15-minute cooldown**.
- In-process state is not durable. On a Render Free cold-start, redeploy, process exit or multiple worker processes, counts reset / do not aggregate. No 24/7 detection, guarantee of delivery or verified real-customer impact.
- The notification path is **non-blocking**: a background coroutine offloads a short-HTTP-timeout Bot API request to a thread. Delivery failures cannot approve, apply, roll back, or alter HTTP response semantics. Under process shutdown the best-effort task may be lost.
- No public test route, no automated remediation and no changes to order V1/V2 history.

## Allowlisted output

The threshold event is machine-generated only:

```json
{"schema":"handoffguard.alert.v1","event":"business_5xx_threshold","environment":"demo","operation":"createOrder","failure_count":3,"window_seconds":300,"timestamp_utc":"2026-10-18T00:00:00+00:00"}
```

The timestamp/count above are **illustrative**, not measured evidence. Telegram receives only demo identifier, operation, window, count, and timestamp. **Never send** URL/path, order/change/customer/actor IDs, input text, auth headers, bot token, chat ID, exception messages, DB URL or traces. Diagnostics log only a static event and operation.

## Owner-only Render configuration (after review and approved merge)

1. Use Telegram's official `@BotFather` to create a new bot, and privately open its chat and press **Start**.
2. Discover **your own numeric private chat ID** without pasting the bot token into browser URLs, chats, GitHub or screenshots. Do not use a shared group or a public channel.
3. In the existing Render service **Environment**, set:
   - `HANDOFFGUARD_ALERT_TELEGRAM_BOT_TOKEN` = private BotFather token
   - `HANDOFFGUARD_ALERT_TELEGRAM_CHAT_ID` = private numeric chat ID
4. Save both as **secure environment settings directly in Render**. Do not commit a `.env`, paste values in an issue, or include them in CI.
5. After human release approval, validate a **harmless test notification** to the owner's own chat using a separately approved manual method. No real order writes, fake HTTP 5xx in Neon, or publicly exposed trigger endpoints. Inspect logs for `alert_sent` but don't claim Telegram delivered it until the owner actually receives the message.

With absent/invalid config, three matched 5xx events emit `alert_suppressed` with reason `channel_not_configured` instead of claiming delivery. Telegram timeout or a failed HTTP response emits `alert_delivery_failed`, without the URL, response body or exception text.

## Evidence required to finish rubric #11

- `python -m pytest -q` within `backend/`, and `bash scripts/test-all.sh` (backend, frontend, build).
- Five GitHub PR CI checks green, with run URLs captured.
- No merge before owner approval: existing `main` may trigger Render auto-deploy.
- Owner confirms a real generic Telegram test message **from the intended channel**, with private details hidden, and reviews Render `alert_sent` evidence and unchanged read-only order V1/V2 after release. Only then mark Issue #18 and rubric #11 closed.
- Limit: this is a course demonstration, not reliable production incident response.

Official Telegram Bot API: https://core.telegram.org/bots/api#sendmessage
Course project rubric: https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md
