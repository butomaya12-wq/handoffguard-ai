# On-call Gate 08 — optional AI triage (educational local synthetic lab)

**Status 2026-10-22:** development draft in [PR #32](https://github.com/butomaya12-wq/handoffguard-ai/pull/32), based on [PR #31](https://github.com/butomaya12-wq/handoffguard-ai/pull/31). **Owner Mac UAT PASS** for one induced isolated local outage -> two distinct Prometheus `up=0` scrapes -> real OpenAI diagnosis -> **automatic one-time fixed backend start using separate prior operator authorization** -> Docker healthy, two fresh `up=1` scrapes and retained FRAME-01 V1/V2 in the local UI. See [full UAT evidence](oncall-autorecover-owner-uat-2026-10-22.md). **No Render deployment, 24/7 scheduler, broad autonomous tools, or guaranteed course grading for criterion #12.**

## Architecture

```text
Prometheus 127.0.0.1:9090 -> oncall.detector.DownDetector
 two distinct failed scrapes -> allowlisted synthetic backend_unavailable event
                            -> oncall.agent (one-shot or --watch)
                         ├── default: log event, NO external model request
                         └── --live + typed approval: OpenAI Responses API
                                      -> JSON schema advice
                                      -> strict enum/length validation
                                      -> default: DISPLAY ONLY
                                      └── optional --auto-recover + separate
                                          preauthorization at startup
                                          -> strict policy, fixed backend only
                                          -> verify Docker exited + two fresh up=0
                                          -> exact compose start backend
                                          -> Docker healthy + two fresh up=1
                                          -> exit after first incident
```

No Docker commands, shells, SQL, customer data, full traces/logs, Render, Neon, CI secrets or arbitrary URLs ever reach the AI module. Only fixed synthetic `environment`, `service`, `signal`, and `human_approval_required` are sent, with `store:false` and a fixed model `gpt-5.4-mini`. The model has **no tool access**, and output is never used as executable code. A failure, refusal, expired/ambiguous signal or invalid advice fails closed. Default mode never calls `oncall.recovery`. In explicit `--auto-recover` mode, the model's allowlisted `recommended_action=request_human_approved_local_backend_start` is only a **necessary condition**, not sufficient authorization: Docker context, fixed Compose service, actually exited state and multiple fresh Prometheus scrapes are checked by independent deterministic code.

## Owner Mac: safe local / no-cost verification

From the repository root on synced `main` at or after the verified 2026-10-22 release (the feature branch was integrated by PR #33):

```bash
python3 -m unittest discover -s oncall/tests -v
python3 -m oncall.agent --demo
python3 -m oncall.agent
```

- `--demo` shows explicitly labelled **fixed offline example**, with no API, no actual LLM inference and no Docker changes; this is for learning and schema demo only.
- Default `python3 -m oncall.agent` reads one real Prometheus health sample; when healthy prints `backend_sample/up`, never calls OpenAI or Docker.
- `--watch` polls every 5 seconds. It prints one event after two distinct scrapes show `up=0`, then exits; by default it reports `ai_analysis_skipped` instead of incurring AI API cost.
- All unit tests use mocked API responses. Passing them verifies integration contracts, **not** a real paid OpenAI call.

## Real AI API trial (NOT authorized or executed by default)

`python3 -m oncall.agent --watch --live` is **opt-in and may incur API charges**. It asks for a separate exact confirmation `SEND ONE SYNTHETIC ALERT TO OPENAI` before listening; if an actual local outage occurs, it makes **at most one** request and exits. Requires `OPENAI_API_KEY` in a private local environment. **Do not paste the key into chats, GitHub issues, commits, screenshots or a shell command**. ChatGPT subscriptions do not automatically grant paid API quota. No token is needed for offline tests; do not ask for one until the owner explicitly elects an API trial.

The owner must separately approve any deliberate local outage of the lab on port 8082; do not use `--watch --live` to generate synthetic outage data by writing customer orders. Do not connect the hosted Render/Neon deployments. Do not assume an existing Hermes VPS can access local Prometheus or Docker; any Hermes integration would require a fresh security design.


## Experimental single-incident preauthorized recovery — owner-UAT-verified on isolated Mac lab

New optional mode, *only from the project root, only on owner's Mac*:

```bash
python3 -m oncall.agent --watch --live --auto-recover
```

This command **does not run without explicit two-part interactive preauthorization** at startup:

1. `SEND ONE SYNTHETIC ALERT TO OPENAI`: permit at most one billable OpenAI diagnosis when a real local Prometheus `up=0` incident is detected.
2. `AUTHORIZE ONE LOCAL BACKEND START`: preauthorize the ONE fixed local lab backend startup later in this process, provided strict independent safety checks pass.

If the private `OPENAI_API_KEY` is absent or the isolated local Compose `backend` is not initially `running/healthy`, the program refuses before requesting consent or making any paid call. The agent watches until one confirmed incident, and exits after that one incident (success, veto, or failure). It is **not** a 24/7 daemon and does not watch multiple services.

If AI advice is malformed, calls for manual investigation or does not recommend a human-approved backend start, **do nothing**. Even if AI recommends recovery, independently check the local Unix Docker context, exact Compose project/filename/service/container; require the container to be `exited` and two distinct fresh `up=0` scrapes. Check state again immediately before the fixed `docker compose start backend`. Afterwards require Docker healthy and two distinct fresh `up=1` scrapes. Return `backend_recovered` with `authorization=explicit_session_preapproval` only if ALL post-checks pass. The AI never constructs Docker commands, and volume deletion/recreation is never attempted.

**Limitations:** No unattended multi-incident schedule, no cloud access, no production incident eligibility. Operator can stop at any time via Ctrl+C. If the model fails or the policy vetoes recovery, backend remains stopped and must be recovered manually after inspection. This is session-level preauthorization, not a new approval prompted at the moment of outage. Owner separately approved the successful single local UAT, and must separately authorize any further deliberate outage or paid API call.

## Proof required for actual agent / rubric #12

- **Done (owner Mac):** real model response against a detected sanitized local synthetic outage (two real distinct Prometheus `up=0` scrapes).
- **Done (owner Mac):** bounded alert → actual model triage → separate operator approval → one exact local backend start → independent health verification and unchanged V1/V2 in UI.
- **Done (owner Mac 2026-10-22):** two-consent-at-launch one-shot `--auto-recover` pathway was exercised on a deliberately stopped isolated lab backend. The same agent process produced genuine `ai_incident_advice` then `backend_recovered` with `authorization=explicit_session_preapproval`. Owner independently saw preserved V1=100 and V2=120 in the UI. Evidence: [UAT report](oncall-autorecover-owner-uat-2026-10-22.md).
- **Still unproven / outside scope:** unattended persistent alert listener, operation after process exit, recovery of arbitrary incidents, remote host or cloud safety and production readiness. The real code executes a narrowly scoped predetermined Docker action, not arbitrary model-generated commands. Course peer-review acceptance remains external.
- **Historical release restriction (superseded 2026-10-22):** PR #32 was previously held in Draft pending owner approval. Its content was subsequently integrated by the single owner-approved squash merge of PR #33. The agent remains **local-only**; merging source code did not authorize cloud/on-prem agent activation, any further intentional outage or paid API inference. Future release changes still require owner approval.

## External contract

The adapter uses the OpenAI Responses API `POST /v1/responses` with `text.format.type="json_schema"` (Structured Outputs) and `store=false`. Verify model availability/billing for the owner's own API project before activating. Official reference: https://developers.openai.com/api/reference/resources/responses/methods/create and https://developers.openai.com/api/docs/guides/structured-outputs .
