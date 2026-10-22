"""No Docker, network, cloud credentials or business data are touched."""
import unittest

from oncall.detector import DownDetector, Sample, State, parse_prometheus


def payload(value="1", timestamp=1_800_000_000, *, labels=None):
    return {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [{
                "metric": labels if labels is not None else {
                    "job": "handoffguard_local_business",
                    "environment": "local_synthetic",
                    "instance": "backend:8000",
                },
                "value": [timestamp, value],
            }],
        },
    }


class ParserTests(unittest.TestCase):
    NOW = 1_800_000_010

    def test_up_and_down(self):
        self.assertEqual(parse_prometheus(payload("1"), now=self.NOW).state, State.UP)
        self.assertEqual(parse_prometheus(payload("0"), now=self.NOW).state, State.DOWN)

    def test_missing_series_fails_closed(self):
        data = payload()
        data["data"]["result"] = []
        self.assertEqual(parse_prometheus(data, now=self.NOW).state, State.UNKNOWN)

    def test_two_series_is_ambiguous(self):
        data = payload()
        data["data"]["result"].append(data["data"]["result"][0])
        self.assertEqual(parse_prometheus(data, now=self.NOW).state, State.UNKNOWN)

    def test_unexpected_target_fails_closed(self):
        self.assertEqual(parse_prometheus(payload("0", labels={
            "job": "another_job", "environment": "local_synthetic",
            "instance": "backend:8000",
        }), now=self.NOW).state, State.UNKNOWN)

    def test_stale_or_future_metric_fails_closed(self):
        self.assertEqual(parse_prometheus(payload("0", self.NOW - 31), now=self.NOW).state, State.UNKNOWN)
        self.assertEqual(parse_prometheus(payload("0", self.NOW + 6), now=self.NOW).state, State.UNKNOWN)

    def test_invalid_values_fail_closed(self):
        for value in ("NaN", "+Inf", "0.5", "wrong"):
            with self.subTest(value=value):
                self.assertEqual(parse_prometheus(payload(value), now=self.NOW).state, State.UNKNOWN)

    def test_malformed_structure_fails_closed(self):
        for data in (None, [], {}, {"status": "error"}, {"status": "success", "data": {}}):
            self.assertEqual(parse_prometheus(data, now=self.NOW).state, State.UNKNOWN)


class DetectorTests(unittest.TestCase):
    NOW = 1_800_000_010

    def test_two_distinct_down_samples_trigger_single_read_only_alert(self):
        monitor = DownDetector()
        self.assertIsNone(monitor.observe(Sample(State.DOWN, self.NOW - 2), now=self.NOW))
        self.assertIsNone(monitor.observe(Sample(State.DOWN, self.NOW - 2), now=self.NOW))
        incident = monitor.observe(Sample(State.DOWN, self.NOW - 1), now=self.NOW)
        self.assertEqual(incident["event"], "backend_unavailable")
        self.assertEqual(incident["action"], "report_only")
        self.assertTrue(incident["human_approval_required"])
        self.assertIsNone(monitor.observe(Sample(State.DOWN, self.NOW), now=self.NOW))

    def test_recovery_rearms_detector(self):
        monitor = DownDetector()
        monitor.observe(Sample(State.DOWN, 1), now=self.NOW)
        self.assertIsNotNone(monitor.observe(Sample(State.DOWN, 2), now=self.NOW))
        monitor.observe(Sample(State.UP, 3), now=self.NOW)
        self.assertIsNone(monitor.observe(Sample(State.DOWN, 4), now=self.NOW))
        self.assertIsNotNone(monitor.observe(Sample(State.DOWN, 5), now=self.NOW))

    def test_unknown_breaks_down_streak_without_firing(self):
        monitor = DownDetector()
        monitor.observe(Sample(State.DOWN, 1), now=self.NOW)
        monitor.observe(Sample(State.UNKNOWN), now=self.NOW)
        self.assertIsNone(monitor.observe(Sample(State.DOWN, 2), now=self.NOW))
        self.assertIsNotNone(monitor.observe(Sample(State.DOWN, 3), now=self.NOW))

    def test_unknown_never_rearms_ongoing_incident(self):
        monitor = DownDetector()
        monitor.observe(Sample(State.DOWN, 1), now=self.NOW)
        monitor.observe(Sample(State.DOWN, 2), now=self.NOW)
        monitor.observe(Sample(State.UNKNOWN), now=self.NOW)
        self.assertIsNone(monitor.observe(Sample(State.DOWN, 3), now=self.NOW))
        self.assertIsNone(monitor.observe(Sample(State.DOWN, 4), now=self.NOW))


if __name__ == "__main__":
    unittest.main()
