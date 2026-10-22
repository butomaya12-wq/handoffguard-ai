# Owner UAT: bounded on-call auto-recovery — 2026-10-22

Source: terminal outputs supplied by the project owner in ChatGPT. No credentials or customer records.

- Scope: isolated local synthetic Docker Compose laboratory only.
- Preparation: 51/51 offline Python tests passed on Mac; owner confirmed an API key was available locally. No API secret recorded.
- Launch: one-shot watch/live/auto-recover mode, with separately typed preauthorization for one OpenAI analysis and one fixed local backend start.
- The owner deliberately stopped ONLY the laboratory backend (Compose confirmed stopped).
- Agent emitted two separate `backend_sample/down` signals and `backend_unavailable` with `two_distinct_prometheus_scrapes_up_zero`, UTC event timestamp `2026-10-22T05:15:20.287813+00:00`.
- A real model reply was emitted: `source=openai_api`, `model=gpt-5.4-mini`, `severity=critical`, `hypothesis=stopped_backend`, `confidence=medium`, `recommended_action=request_human_approved_local_backend_start`.
- The same agent process subsequently emitted `backend_recovered`, `authorization=explicit_session_preapproval`, and `verification=docker_healthy_and_two_distinct_up_scrapes`. The operator did not issue a separate recovery command after the outage.
- **PASS**: one preauthorized, AI-mediated local incident-to-fixed-recovery cycle, independently checked by deterministic code.
- Limitations: not an unattended persistent on-call daemon; AI has no Docker command tools; no arbitrary remediation or production operation. The model's `automatic_repair=false` field concerns its own read-only advice, not the separately preauthorized deterministic recovery.
- **Pending**: inspect local frontend to confirm immutable FRAME-01 V1=100 and V2=120 history remains intact after this specific recovery trial. No claim of verified order history yet for this attempt.
