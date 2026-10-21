"""Safety/negative tests run without a Docker daemon or network access."""
import json
import unittest
from unittest.mock import Mock, patch

from oncall import recovery
from oncall.detector import Sample, State


def compose_row(*, state="exited", health="", service="backend", project=None):
    return json.dumps([{
        "Project": project or recovery.PROJECT,
        "Service": service,
        "Name": recovery.CONTAINER,
        "State": state,
        "Health": health,
    }])


class RecoverySafetyTests(unittest.TestCase):
    def test_denied_approval_never_touches_docker(self):
        probe = Mock(side_effect=AssertionError("no commands should run"))
        self.assertEqual(
            recovery.perform(approved=False, check_state=probe)["reason"],
            "human_approval_required",
        )
        probe.assert_not_called()

    def test_running_backend_must_not_be_restarted(self):
        start = Mock()
        result = recovery.perform(
            approved=True,
            check_state=lambda: ("running", "healthy"),
            verify_metrics=lambda _: True,
            run_start=start,
        )
        self.assertEqual(result["reason"], "backend_not_stopped")
        start.assert_not_called()

    def test_unknown_or_unverified_outage_refuses_start(self):
        start = Mock()
        result = recovery.perform(
            approved=True,
            check_state=lambda: ("exited", ""),
            verify_metrics=lambda _: False,
            run_start=start,
        )
        self.assertEqual(result["reason"], "outage_unverified")
        start.assert_not_called()

    def test_state_changed_refuses_start(self):
        start = Mock()
        states = iter([("exited", ""), ("running", "healthy")])
        result = recovery.perform(
            approved=True,
            check_state=lambda: next(states),
            verify_metrics=lambda _: True,
            run_start=start,
        )
        self.assertEqual(result["reason"], "backend_state_changed")
        start.assert_not_called()

    def test_allowlisted_local_start_requires_postverification(self):
        start = Mock()
        states = iter([("exited", ""), ("exited", ""), ("running", "healthy")])
        observed = []
        def verify(state):
            observed.append(state)
            return True
        result = recovery.perform(
            approved=True,
            check_state=lambda: next(states),
            verify_metrics=verify,
            run_start=start,
        )
        self.assertEqual(result["event"], "backend_recovered")
        self.assertEqual(observed, [State.DOWN, State.UP])
        start.assert_called_once_with()

    def test_no_false_success_when_post_recovery_scrape_missing(self):
        start = Mock()
        states = iter([("exited", ""), ("exited", ""), ("running", "healthy")])
        result = recovery.perform(
            approved=True,
            check_state=lambda: next(states),
            verify_metrics=lambda state: state is State.DOWN,
            run_start=start,
        )
        self.assertEqual(result["event"], "recovery_unverified")
        start.assert_called_once_with()

    def test_start_command_failure_is_reported_without_leak(self):
        def failed():
            raise recovery.UnsafeRecovery("docker_command_failed")
        result = recovery.perform(
            approved=True,
            check_state=lambda: ("exited", ""),
            verify_metrics=lambda _: True,
            run_start=failed,
        )
        self.assertEqual(result["event"], "recovery_failed")

    def test_remote_docker_host_is_rejected_without_subprocess(self):
        with patch.dict(recovery.os.environ, {"DOCKER_HOST": "tcp://remote:2376"}):
            with patch.object(recovery.subprocess, "run") as invoked:
                with self.assertRaisesRegex(recovery.UnsafeRecovery, "docker_environment_override"):
                    recovery.docker_command("ps")
                invoked.assert_not_called()

    def test_invalid_target_is_rejected(self):
        with patch.object(recovery, "compose", return_value=compose_row(service="other")):
            with self.assertRaisesRegex(recovery.UnsafeRecovery, "unexpected_container_state"):
                recovery.container_state()

    def test_multiple_containers_are_rejected(self):
        row = json.loads(compose_row())[0]
        with patch.object(recovery, "compose", return_value=json.dumps([row, row])):
            with self.assertRaisesRegex(recovery.UnsafeRecovery, "unexpected_container_state"):
                recovery.container_state()

    def test_explicit_container_status_is_accepted(self):
        with patch.object(recovery, "compose", return_value=compose_row(state="running", health="healthy")):
            self.assertEqual(recovery.container_state(), ("running", "healthy"))

    def test_two_distinct_metric_scrapes_are_required(self):
        samples = iter([
            Sample(State.DOWN, 100),
            Sample(State.DOWN, 100),
            Sample(State.DOWN, 105),
        ])
        ticks = iter([0, 1, 2, 3, 4, 5])
        self.assertTrue(recovery.distinct_samples(
            State.DOWN, fetch=lambda: next(samples),
            clock=lambda: next(ticks), sleep=lambda _: None,
        ))

    def test_unknown_data_rejects_recovery(self):
        values = iter([Sample(State.DOWN, 100), Sample(State.UNKNOWN)])
        self.assertFalse(recovery.distinct_samples(
            State.DOWN, fetch=lambda: next(values),
            clock=lambda: 0, sleep=lambda _: None,
        ))


if __name__ == "__main__":
    unittest.main()
