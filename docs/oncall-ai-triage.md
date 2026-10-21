# On-call Gate 08 — optional AI triage (educational local synthetic lab)

**Status:** development draft in PR #32, based on integrated PR #31. NO cloud deployment, autonomous recovery, 24/7 scheduler or proof of criterion #12. The owner's previously verified outage recovery was through the **deterministic human-approved** `oncall.recovery`, NOT an LLM.

## Architecture

```text
Prometheus 127.0.0.1:9090 -> oncall.detector.DownDetector
 two distinct failed scrapes -> allowlisted synthetic backend_unavailable event
                            -> oncall.agent (one-shot or --watch)
                         ├── default: log event, NO external model request
                         └── --live + typed approval: OpenAI Responses API
                                      -> JSON schema advice
                                      -> strict enum/length validation
                                      -> DISPLAY ONLY (no repair action)
```

No Docker commands, shells, SQL, customer data, full traces/logs, Render, Neon, CI secrets or arbitrary URLs ever reach the AI module. Only fixed synthetic `environment`, `service`, `signal`, and `human_approval_required` are sent, with `store:false` and a fixed model `gpt-5.4-mini`. The model has **no tool access**, and output is never used as executable code. A failure, refusal, expired/ambiguous signal or invalid advice fails closed; do not automatically call `oncall.recovery`.

## Owner Mac: safe local / no-cost verification

From repository root on `feature/oncall-agent-safe-local-design-issue28`, after `git pull --ff-only`:

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

## Proof required for actual agent / rubric #12

- Verify a real model response against a real sanitized local synthetic outage.
- Demonstrate bounded alert → actual model triage → separate operator approval → one exact local backend start → independent health verification and unchanged V1/V2.
- Add explicit evidence timestamps, no arbitrary Docker shell or customer edits, no secret-bearing output. A manually chained prototype does **not** count as an automatically awakened agent. Add a narrowly-scoped coordinator later if feasible.
- Keep PR #32 draft, do not merge into main or deploy without owner permission.

## External contract

The adapter uses the OpenAI Responses API `POST /v1/responses` with `text.format.type="json_schema"` (Structured Outputs) and `store=false`. Verify model availability/billing for the owner's own API project before activating. Official reference: https://developers.openai.com/api/reference/resources/responses/methods/create and https://developers.openai.com/api/docs/guides/structured-outputs .
