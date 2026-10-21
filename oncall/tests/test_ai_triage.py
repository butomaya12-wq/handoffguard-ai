"""Read-only AI adapter tests with a mocked network; never use real API keys."""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from oncall import agent, ai_triage
from oncall.ai_triage import TriageUnavailable

VALID = {
    "severity": "critical",
    "hypothesis": "unknown",
    "confidence": "low",
    "recommended_action": "inspect_backend_status",
    "explanation_ru": "Prometheus не получил метрики; причина пока неизвестна.",
}


class Response:
    def __init__(self, data: dict):
        self.body = json.dumps(data).encode()
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def read(self, size):
        return self.body[:size]


def api_result(advice=None):
    return {"status": "completed", "output": [
        {"type": "message", "content": [{"type": "output_text",
                                         "text": json.dumps(advice or VALID)}]},
    ]}


class SanitizationTests(unittest.TestCase):
    def test_only_allowlisted_fixed_values_reach_model(self):
        event = agent.example_incident()
        event["private_customer_name"] = "DO NOT SEND THIS"
        event["secret_token"] = "DO NOT SEND THIS TOO"
        payload = ai_triage.request_payload(event)
        self.assertNotIn("DO NOT SEND", json.dumps(payload))
        self.assertEqual(payload["model"], ai_triage.MODEL)
        self.assertFalse(payload["store"])
        self.assertEqual(payload["tools"], [])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")

    def test_wrong_incident_rejected(self):
        event = agent.example_incident()
        for field, value in (
            ("environment", "production"),
            ("service", "neon"),
            ("evidence", "user says outage"),
            ("human_approval_required", False),
            ("action", "execute_shell"),
        ):
            with self.subTest(field=field):
                dirty = dict(event, **{field: value})
                with self.assertRaisesRegex(TriageUnavailable, "invalid_incident"):
                    ai_triage.sanitize_incident(dirty)

    def test_bad_timestamp_rejected(self):
        event = agent.example_incident()
        event["observed_at_utc"] = "not-a-time"
        with self.assertRaisesRegex(TriageUnavailable, "invalid_timestamp"):
            ai_triage.sanitize_incident(event)

    def test_output_schema_rejects_unexpected_action(self):
        illegal = dict(VALID, recommended_action="docker rm -f everything")
        with self.assertRaisesRegex(TriageUnavailable, "invalid_model_output"):
            ai_triage.validate_advice(illegal)

    def test_output_schema_rejects_extra_and_oversized(self):
        with self.assertRaises(TriageUnavailable):
            ai_triage.validate_advice(dict(VALID, executable_shell="docker"))
        with self.assertRaises(TriageUnavailable):
            ai_triage.validate_advice(dict(VALID, explanation_ru="x" * 241))

    def test_refusal_and_incomplete_response_fail_closed(self):
        with self.assertRaises(TriageUnavailable):
            ai_triage.extract_advice({"status": "incomplete", "output": []})
        with self.assertRaises(TriageUnavailable):
            ai_triage.extract_advice({
                "status": "completed", "output": [
                    {"type": "message", "content": [{"type": "refusal"}]},
                ],
            })

    def test_model_output_is_structurally_validated(self):
        parsed = ai_triage.extract_advice(api_result())
        self.assertEqual(parsed, VALID)

    def test_api_call_mock_sends_only_sanitized_incident(self):
        captured = []
        def fake_sender(request, timeout):
            captured.append((request, timeout))
            return Response(api_result())
        result = ai_triage.analyze_incident(
            dict(agent.example_incident(), private="SECRET"),
            token="fake-test-token", transport=fake_sender,
        )
        self.assertEqual(result["event"], "ai_incident_advice")
        self.assertFalse(result["automatic_repair"])
        self.assertTrue(result["human_approval_required"])
        self.assertEqual(len(captured), 1)
        request, timeout = captured[0]
        self.assertEqual(request.full_url, ai_triage.API_ENDPOINT)
        self.assertNotIn("SECRET", request.data.decode())
        self.assertEqual(timeout, 20)

    def test_network_failure_is_redacted(self):
        def fail(_request, timeout):
            raise RuntimeError("my-secret-key-was-in-error")
        with self.assertRaisesRegex(TriageUnavailable, "^model_request_failed$"):
            ai_triage.analyze_incident(
                agent.example_incident(), token="fake-test-token", transport=fail,
            )

    def test_missing_key_fails_without_network(self):
        with patch.dict(ai_triage.os.environ, {"OPENAI_API_KEY": ""}):
            with patch.object(ai_triage, "urlopen") as send:
                with self.assertRaisesRegex(TriageUnavailable, "api_key_not_configured"):
                    ai_triage.analyze_incident(agent.example_incident())
                send.assert_not_called()


class CoordinatorTests(unittest.TestCase):
    def test_default_on_healthy_sample_never_calls_model(self):
        with patch.object(agent, "fetch_backend_sample", return_value=ai_triage_event_up()):
            with patch.object(agent, "analyze_incident") as analysis:
                with redirect_stdout(io.StringIO()) as sink:
                    self.assertEqual(agent.main([]), 0)
                self.assertIn('"state":"up"', sink.getvalue())
                analysis.assert_not_called()

    def test_offline_demo_never_calls_model(self):
        with patch.object(agent, "analyze_incident") as analysis:
            with redirect_stdout(io.StringIO()) as sink:
                self.assertEqual(agent.main(["--demo"]), 0)
            self.assertIn('"source":"fixed_fixture_not_ai"', sink.getvalue())
            analysis.assert_not_called()

    def test_live_mode_requires_explicit_operator_approval(self):
        with patch("builtins.input", return_value="no"):
            with patch.object(agent, "analyze_incident") as analysis:
                with redirect_stdout(io.StringIO()) as sink:
                    self.assertEqual(agent.main(["--live"]), 1)
                self.assertIn("explicit_consent_required", sink.getvalue())
                analysis.assert_not_called()


def ai_triage_event_up():
    from oncall.detector import Sample, State
    return Sample(State.UP, 1_800_000_000)


if __name__ == "__main__":
    unittest.main()
