# Gate 08 — On-call responder: safe local outage / recovery experiment

**Status (2026-10-21): DESIGN / GO for isolated prototype only. No responder code, LLM, simulated outage, autonomous repair, customer access, CI proof, or rubric #12 credit yet.**

Parent: [Issue #28](../issues/28). Experimental baseline: [Draft PR #31](../pull/31), containing the new role UI and optional local Prometheus/Jaeger lab. This design branch is separate; do not merge into `main` or deploy to Render/Neon.

## User-facing objective

Prove with durable timestamped evidence: **backend alive → outage actually detected → bounded responder receives evidence → human approves one allowlisted recovery → backend healthy → business records persist**, without touching customer data or cloud systems. Later add actual LLM-assisted **read-only** diagnosis (from fixed sanitized metrics) and test whether rubric #12's **agent wakes on an alert and fixes a real incident** is satisfied; a rule-based script and Telegram notification are not automatically an AI agent.

## Why this incident

The already-running local synthetic lab contains separate named volumes: `lab_orders`, `lab_metrics` and `lab_traces`. Existing Prometheus job `handoffguard_local_business` scrapes the backend's internal `/internal/metrics` every 5 seconds. When the **backend container is intentionally stopped with owner consent** and no restart policy is configured, the job's `up` series becomes `0`; when a stopped backend is started again and the health check succeeds, it becomes `1`. We can diagnose and restore **actual availability** while leaving historical V1/V2 SQLite rows untouched.

This deliberately induced *real service outage in a disposable local lab* is not evidence of a real customer incident. Reproducing a 5xx exception by changing an order, altering an invoice or purposely corrupting a database is prohibited.

## Concrete detector and bounded action

- Observe `up{job="handoffguard_local_business",environment="local_synthetic"}` from `http://127.0.0.1:9090/api/v1/query`.
- Require the exact single expected Prometheus target and two consecutive failed scrapes. If the query is unreachable, empty, ambiguous, or malformed, **report unknown**, never claim `up=0` or execute an action.
- Serialize a minimal event: synthetic lab, alert type `backend_unavailable`, first-observed timestamp, source job/metric, current `up` state. Do not include order/customer text, tokens, URLs from requests, raw exception bodies, cloud hostnames or credentials.
- Host-side runner (not a Docker container with access to Docker socket) checks for an explicitly owned local repo and fixed local Compose project name `handoffguard-observability-lab`. This still inherits the user's host Docker privileges; audit code accordingly.
- **Read-only default**: evidence collection and safe diagnosis only. Any change requires fresh explicit human confirmation, with no silent approval / unattended loop.
- Only permitted recovery action: via argument-vector subprocess (no `shell=True`, user-controlled command/path/target), `docker compose -f docker-compose.observability.yml start backend` with validated fixed local project and a hard-coded service `backend`. No `up --build`, `restart` of unrelated services, `down`, `down -v`, `docker system prune`, SQL writes, Render API or Neon credentials.
- Require the target to be **stopped** rather than an unhealthy-but-running service before permitting `start`; no speculative restart of a running backend, no clearing alerts as "fixed".
- Verify recovery by actual Compose `backend: Healthy` plus two Prometheus scrapes with `up=1`; and read-only confirmation that the synthetic test order's V1/V2 history remains available. Fail closed on missing proof.
- Emit simple readable report: `detected`, `approved` or `approval_required`, `attempted_action`, `verification`, `outcome`. No claim of recovery without independent positive evidence.

## Proposed owner Mac UAT (NOT YET AUTHORIZED / EXECUTED)

1. Capture baseline `docker compose -f docker-compose.observability.yml ps`; Prometheus job `up=1`; frontend visible at `127.0.0.1:8082`; V1 and V2 in history.
2. Owner **explicitly approves temporary local outage** and manually executes `docker compose -f docker-compose.observability.yml stop backend`. This interrupts *only* the synthetic app at 8082; does **not** delete volumes. Ordinary 8080 and cloud unaffected.
3. Let at least two 5 s Prometheus scrapes occur; verify `up=0` and alert detection by responder. No recovery action without fresh owner approval.
4. Owner approves only static `start backend` action; bounded responder performs it once.
5. Verify Compose backend health and `up=1` in repeated scrapes; verify prior synthetic V1/V2 rows through UI or read-only API.
6. Deliberately test denied/malformed alert, wrong job/environment, unavailable Prometheus, missing consent, stopped Jaeger, already-running backend, wrong project directory. All fail closed; no Docker restart, tokens, or customer data.
7. Preserve one audit/evidence log without secret-bearing payload. Run all integrated backend/frontend/Compose/Postgres/Observability CI and owner Mac tests on separate draft PR once code exists.

## AI boundary

A model may be used to classify/describe a *sanitized structured alert* and suggest investigation steps, but it must not choose arbitrary Docker CLI arguments or gain access to the host Docker socket, cloud credentials, SQL or full logs. Until a real model is invoked with a tool-constrained repair step and an evidenced recovery, call implementation a **bounded on-call responder prototype**, not a proven autonomous AI agent; course rubric #12 remains unearned.

## Explicit stop/go recommendation

**GO:** design and code a local-only, read-only detector with full negative tests in a separate branch.

**STOP pending owner approval:** temporarily stop the existing 8082 backend; perform any recovery action that changes running containers; connect Telegram, an AI API, Hermes VPS or any live service; merge to main or deploy. In particular, do not disrupt the ongoing Mac UAT order history without the owner's informed approval.

**Not a production pager:** this lab's Prometheus and Jaeger store roughly 24 hours of telemetry and do not provide continuous externally hosted monitoring. A host-side watcher works only while the owner's Mac and watcher remain running.

## Stage 2 implementation (2026-10-21; still unproved on owner Mac)

`oncall/recovery.py` is a **human-operated recovery runner**, NOT an autonomous AI agent. It does not include an LLM or run automatically upon an incident. No recovery has yet been performed by this program in the owner's local lab.

### Read-only preflight (safe while healthy)

```bash
python3 -m oncall.recovery
```

This verifies the exact local Docker Unix socket, fixed Docker Compose project/service identity and one backend container; it prints a sanitized status without changing services. Never copy credentials or raw Docker environment variables into chat.

### Recovery test (requires NEW owner consent to temporarily stop 8082)

Only after a separate explicit authorization to interrupt the local synthetic backend, reproduce a confirmed `down` condition using the prior tested `docker compose -f docker-compose.observability.yml stop backend`. The runner then requires **both**:
1. Fresh `up=0` observations with two distinct Prometheus scrape timestamps and a stopped *exact* backend container.
2. The operator executes `python3 -m oncall.recovery --apply` and types the exact phrase `START LOCAL BACKEND` at the interactive prompt. No silent default approval. Revalidate the stopped container and the two down scrapes immediately before the single fixed start command.

The only mutating command in the runner is a fixed, local-only `docker compose -p handoffguard-observability-lab -f <repository-local-file> start backend`. Remote Docker contexts, env overrides and unexpected container/project metadata are rejected; the command is never assembled from model text or user-input strings. A successful result requires **both** Docker healthy and two distinct Prometheus `up=1` scrapes. Missing evidence produces `recovery_unverified` rather than falsely claiming success. Manually recheck V1/V2 preservation via the existing synthetic order's History screen.

### Scope and next gates

- The owner has previously manually demonstrated `stop backend → backend_unavailable → manual start backend → up → V1/V2 preserved`; that **does not** prove the newly added runner works end-to-end.
- Safety tests simulate subprocess outcomes; those tests do **not** exercise live Docker start.
- Separate actual Mac UAT with explicit consent is required before representing the runner as proven.
- The runner is deterministic and human-approved. To legitimately claim an **AI agent**, a bounded agent must actually receive the alert, interpret sanitized evidence with a model, and use a restricted tool under owner approval. No freeform command execution or cloud access.
