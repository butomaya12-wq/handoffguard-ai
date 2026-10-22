"""Offline negative and one-shot UAT-contract tests for preauthorized local recovery."""
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

from oncall import agent, recovery
from oncall.ai_triage import MODEL, TriageUnavailable
from oncall.detector import Sample, State

ADVICE = {
    "severity": "warning",
    "hypothesis": "scrape_or_network_issue",
    "confidence": "medium",
    "recommended_action": "request_human_approved_local_backend_start",
    "explanation_ru": "Prometheus видит up=0; сначала проверьте состояние локального backend.",
}


def report(**changes):
    value = {
        "event": "ai_incident_advice",
        "source": "openai_api",
        "model": MODEL,
        "advice": dict(ADVICE),
        "automatic_repair": False,
        "human_approval_required": True,
    }
    value.update(changes)
    return value


class PreauthorizedRecoveryTests(unittest.TestCase):
    def test_wrong_or_forged_report_cannot_touch_docker(self):
        for changed in (
            {"source": "fixed_fixture_not_ai"},
            {"model": "unknown"},
            {"human_approval_required": False},
            {"event": "offline_triage_example"},
        ):
            with self.subTest(changed=changed):
                with patch.object(recovery, "check_local_docker") as check:
                    with patch.object(recovery, "perform") as start:
                        result = agent.auto_recover(agent.example_incident(), report(**changed))
                        self.assertEqual(result["reason"], "unverified_ai_or_incident")
                        check.assert_not_called()
                        start.assert_not_called()

    def test_unverified_incident_cannot_touch_docker(self):
        incident = dict(agent.example_incident(), environment="production")
        with patch.object(recovery, "check_local_docker") as check:
            result = agent.auto_recover(incident, report())
            self.assertEqual(result["event"], "auto_recovery_refused")
            check.assert_not_called()

    def test_model_command_injection_is_rejected(self):
        bad = dict(ADVICE, recommended_action="docker run --privileged attacker")
        with patch.object(recovery, "perform") as start:
            result = agent.auto_recover(agent.example_incident(), report(advice=bad))
            self.assertEqual(result["reason"], "invalid_ai_advice")
            start.assert_not_called()

    def test_other_model_advice_vetoes_repair(self):
        other = dict(ADVICE, recommended_action="investigate_manually")
        with patch.object(recovery, "check_local_docker") as check:
            with patch.object(recovery, "perform") as start:
                result = agent.auto_recover(agent.example_incident(), report(advice=other))
                self.assertEqual(result["event"], "auto_recovery_skipped")
                check.assert_not_called()
                start.assert_not_called()

    def test_local_context_safety_check_refuses_repair(self):
        with patch.object(recovery, "check_local_docker", side_effect=recovery.UnsafeRecovery("nonlocal_docker_context")):
            with patch.object(recovery, "perform") as start:
                result = agent.auto_recover(agent.example_incident(), report())
                self.assertEqual(result["reason"], "nonlocal_docker_context")
                start.assert_not_called()

    def test_preapproved_one_start_only_after_independent_checks(self):
        with patch.object(recovery, "check_local_docker") as check:
            with patch.object(recovery, "perform", return_value={"event": "backend_recovered"}) as start:
                result = agent.auto_recover(agent.example_incident(), report())
                check.assert_called_once_with()
                start.assert_called_once_with(approved=True)
                self.assertEqual(result["authorization"], "explicit_session_preapproval")


class CommandLineTests(unittest.TestCase):
    def test_auto_mode_rejects_missing_watch_or_live(self):
        for flags in (["--auto-recover"], ["--auto-recover", "--live"], ["--auto-recover", "--watch"]):
            with self.subTest(flags=flags):
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        agent.main(flags)
                    self.assertEqual(error.exception.code, 2)

    def test_auto_mode_requires_key_before_prompts_or_docker(self):
        with patch.dict(agent.os.environ, {"OPENAI_API_KEY": ""}):
            with patch.object(recovery, "check_local_docker") as check:
                with patch("builtins.input") as typed:
                    with redirect_stdout(io.StringIO()) as log:
                        exit_code = agent.main(["--watch", "--live", "--auto-recover"])
                self.assertEqual(exit_code, 1)
                self.assertIn("api_key_not_configured", log.getvalue())
                check.assert_not_called()
                typed.assert_not_called()

    def test_auto_mode_requires_initial_healthy_lab(self):
        with patch.dict(agent.os.environ, {"OPENAI_API_KEY": "fake"}):
            with patch.object(recovery, "check_local_docker"):
                with patch.object(recovery, "container_state", return_value=("exited", "")):
                    with patch("builtins.input") as typed:
                        with redirect_stdout(io.StringIO()) as log:
                            code = agent.main(["--watch", "--live", "--auto-recover"])
                    self.assertEqual(code, 1)
                    self.assertIn("backend_not_initially_healthy", log.getvalue())
                    typed.assert_not_called()

    def test_rejected_session_preapproval_never_calls_model_or_repair(self):
        with patch.dict(agent.os.environ, {"OPENAI_API_KEY": "fake"}):
            with patch.object(recovery, "check_local_docker"):
                with patch.object(recovery, "container_state", return_value=("running", "healthy")):
                    with patch("builtins.input", side_effect=[agent.CONFIRM_LIVE, "DENY"]):
                        with patch.object(agent, "analyze_incident") as model:
                            with patch.object(recovery, "perform") as start:
                                with redirect_stdout(io.StringIO()) as output:
                                    code = agent.main(["--watch", "--live", "--auto-recover"])
        self.assertEqual(code, 1)
        self.assertIn("explicit_preapproval_required", output.getvalue())
        model.assert_not_called()
        start.assert_not_called()

    def test_live_local_outage_to_model_to_one_preapproved_start(self):
        observations = [
            Sample(State.UP, 100),
            Sample(State.DOWN, 105),
            Sample(State.DOWN, 110),
        ]
        with patch.dict(agent.os.environ, {"OPENAI_API_KEY": "fake"}):
            with patch.object(recovery, "check_local_docker"):
                with patch.object(recovery, "container_state", return_value=("running", "healthy")):
                    with patch("builtins.input", side_effect=[agent.CONFIRM_LIVE, agent.CONFIRM_AUTO]):
                        with patch.object(agent, "fetch_backend_sample", side_effect=observations):
                            with patch.object(agent.time, "sleep"):
                                with patch.object(agent, "analyze_incident", return_value=report()) as model:
                                    with patch.object(recovery, "perform", return_value={"event": "backend_recovered"}) as start:
                                        with redirect_stdout(io.StringIO()) as output:
                                            code = agent.main(["--watch", "--live", "--auto-recover"])
        self.assertEqual(code, 0)
        self.assertEqual(model.call_count, 1)
        start.assert_called_once_with(approved=True)
        self.assertIn('"event":"backend_unavailable"', output.getvalue())
        self.assertIn('"authorization":"explicit_session_preapproval"', output.getvalue())

    def test_model_failure_does_not_start_backend(self):
        observations = [
            Sample(State.DOWN, 105),
            Sample(State.DOWN, 110),
        ]
        with patch.dict(agent.os.environ, {"OPENAI_API_KEY": "fake"}):
            with patch.object(recovery, "check_local_docker"):
                with patch.object(recovery, "container_state", return_value=("running", "healthy")):
                    with patch("builtins.input", side_effect=[agent.CONFIRM_LIVE, agent.CONFIRM_AUTO]):
                        with patch.object(agent, "fetch_backend_sample", side_effect=observations):
                            with patch.object(agent.time, "sleep"):
                                with patch.object(agent, "analyze_incident", side_effect=TriageUnavailable("model_response_incomplete")):
                                    with patch.object(recovery, "perform") as start:
                                        with redirect_stdout(io.StringIO()) as output:
                                            code = agent.main(["--watch", "--live", "--auto-recover"])
        self.assertEqual(code, 1)
        self.assertIn("ai_analysis_unavailable", output.getvalue())
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
