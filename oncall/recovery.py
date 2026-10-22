"""Human-approved, single-service recovery for the isolated HandoffGuard lab.

The module is deliberately NOT an autonomous agent. It cannot choose commands,
reach Docker remotely, change orders, modify other services, or self-approve.
A successful check requires live Compose health AND two distinct Prometheus
scrapes after the recovery action.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Callable

from .detector import Sample, State, fetch_backend_sample

PROJECT = "handoffguard-observability-lab"
SERVICE = "backend"
CONTAINER = "handoffguard-observability-lab-backend-1"
CONFIRMATION = "START LOCAL BACKEND"
ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.observability.yml"
OBSERVATION_TIMEOUT = 25
RECOVERY_TIMEOUT = 45


class UnsafeRecovery(RuntimeError):
    """A diagnostic failure or unmet safety precondition. No secrets included."""


def docker_command(*args: str, timeout: int = 12) -> str:
    """Execute only internally chosen arguments against a verified local socket."""
    env = os.environ.copy()
    for item in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        if env.get(item):
            raise UnsafeRecovery("docker_environment_override")
    # These variables may override a Compose project/config even with a fixed file.
    for item in tuple(env):
        if item.startswith("COMPOSE_"):
            env.pop(item)
    try:
        result = subprocess.run(
            ["docker", *args], cwd=ROOT, env=env,
            text=True, capture_output=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise UnsafeRecovery("docker_command_unavailable") from None
    if result.returncode != 0 or len(result.stdout) > 8192:
        # Never include raw Docker output: it may contain confidential context.
        raise UnsafeRecovery("docker_command_failed")
    return result.stdout.strip()


def check_local_docker() -> None:
    if COMPOSE.is_symlink() or not COMPOSE.is_file():
        raise UnsafeRecovery("compose_file_missing_or_symlink")
    # A fixed project name and a fixed local Unix socket. Remote TCP/SSH rejected.
    if not COMPOSE.read_text(encoding="utf-8").startswith(
        "# Isolated opt-in observability lab."
    ):
        raise UnsafeRecovery("unexpected_compose_file")
    endpoint = docker_command(
        "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"
    )
    if not endpoint.startswith("unix:///") or "\n" in endpoint:
        raise UnsafeRecovery("nonlocal_docker_context")


def compose(*arguments: str, timeout: int = 12) -> str:
    return docker_command(
        "compose", "-p", PROJECT, "-f", str(COMPOSE), *arguments,
        timeout=timeout,
    )


def container_state() -> tuple[str, str]:
    """Read one exact project/service/container; reject unexpected structures."""
    raw = compose("ps", "--all", "--format", "json", SERVICE)
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list) or len(value) != 1:
            raise ValueError("wrong number of services")
        obj = value[0]
        if not isinstance(obj, dict) or any(
            obj.get(k) != v for k, v in (
                ("Project", PROJECT), ("Service", SERVICE), ("Name", CONTAINER)
            )
        ):
            raise ValueError("wrong service")
        state = obj.get("State")
        health = obj.get("Health", "")
        if state not in ("running", "exited") or not isinstance(health, str):
            raise ValueError("unknown container state")
        return state, health
    except (ValueError, TypeError):
        raise UnsafeRecovery("unexpected_container_state") from None


def distinct_samples(
    desired: State,
    *,
    count: int = 2,
    timeout: int = OBSERVATION_TIMEOUT,
    fetch: Callable[[], Sample] = fetch_backend_sample,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """Require different real scrape timestamps, never two polls of one result."""
    seen: set[float] = set()
    deadline = clock() + timeout
    while clock() < deadline:
        sample = fetch()
        if sample.state is State.UNKNOWN:
            return False
        if sample.state is not desired:
            return False
        if sample.sampled_at is None:
            return False
        seen.add(sample.sampled_at)
        if len(seen) >= count:
            return True
        sleep(2)
    return False


def perform(
    *,
    approved: bool,
    verify_metrics: Callable[[State], bool] = lambda state: distinct_samples(state),
    check_state: Callable[[], tuple[str, str]] = container_state,
    run_start: Callable[[], str] = lambda: compose("start", SERVICE, timeout=35),
) -> dict:
    """Only a STOPPED, confirmed down synthetic backend may be started."""
    if not approved:
        return {"event": "recovery_refused", "reason": "human_approval_required"}
    state, health = check_state()
    if state != "exited":
        return {"event": "recovery_refused", "reason": "backend_not_stopped"}
    if not verify_metrics(State.DOWN):
        return {"event": "recovery_refused", "reason": "outage_unverified"}
    # Detect a concurrent operator start between the two checks.
    if check_state()[0] != "exited":
        return {"event": "recovery_refused", "reason": "backend_state_changed"}
    try:
        run_start()
    except UnsafeRecovery:
        return {"event": "recovery_failed", "reason": "start_command_failed"}
    deadline = time.monotonic() + RECOVERY_TIMEOUT
    while time.monotonic() < deadline:
        try:
            state, health = check_state()
        except UnsafeRecovery:
            return {"event": "recovery_unverified", "reason": "state_unavailable"}
        if state == "running" and health == "healthy":
            break
        time.sleep(2)
    else:
        return {"event": "recovery_unverified", "reason": "backend_not_healthy"}
    if not verify_metrics(State.UP):
        return {"event": "recovery_unverified", "reason": "prometheus_up_unverified"}
    return {
        "event": "backend_recovered",
        "environment": "local_synthetic",
        "service": SERVICE,
        "action": "approved_single_backend_start",
        "verification": "docker_healthy_and_two_distinct_up_scrapes",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or human-approve fixed local synthetic backend start"
    )
    parser.add_argument("--apply", action="store_true",
                        help="Request an explicitly confirmed start of stopped lab backend")
    args = parser.parse_args(argv)
    try:
        check_local_docker()
        state, health = container_state()
        print(json.dumps({
            "event": "local_backend_status", "state": state, "health": health,
            "recovery": "not_needed" if state == "running" else "approval_required",
        }, separators=(",", ":")), flush=True)
        if not args.apply:
            return 0
        if state != "exited":
            print('{"event":"recovery_refused","reason":"backend_not_stopped"}')
            return 1
        if not distinct_samples(State.DOWN):
            print('{"event":"recovery_refused","reason":"outage_unverified"}')
            return 1
        print(
            "Only local synthetic backend will start; V1/V2 volumes remain unchanged.\n"
            f"Type exactly {CONFIRMATION!r} to authorize once: ",
            end="", flush=True,
        )
        try:
            approval = input()
        except (EOFError, KeyboardInterrupt):
            approval = ""
        # Recheck the state and scrape evidence in perform() before action.
        result = perform(approved=(approval == CONFIRMATION))
        print(json.dumps(result, separators=(",", ":")), flush=True)
        return 0 if result.get("event") == "backend_recovered" else 1
    except UnsafeRecovery as exc:
        print(json.dumps({"event": "recovery_refused", "reason": str(exc)},
                         separators=(",", ":")), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
