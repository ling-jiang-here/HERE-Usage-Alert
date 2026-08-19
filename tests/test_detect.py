from datetime import date, datetime, timedelta, timezone
import unittest

from usage_alert.detect import detect_anomalies
from usage_alert.models import DetectionConfig, UsageRecord


class DetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = DetectionConfig(30, 14, 1000, 0.5, 3.5, 0.5, 2.0)
        self.target = date(2026, 8, 18)

    def record(self, usage_date: date, quantity: float) -> UsageRecord:
        return UsageRecord(
            usage_date, "transactions", quantity, "transactions", "routing", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"routing"}',
            datetime.now(timezone.utc),
        )

    def test_flags_large_spike_with_stable_history(self) -> None:
        history = [self.record(self.target - timedelta(days=index), 10_000) for index in range(1, 15)]
        anomalies = detect_anomalies(history + [self.record(self.target, 40_000)], self.target, self.config)
        self.assertEqual(1, len(anomalies))
        self.assertEqual("critical", anomalies[0].severity)

    def test_skips_series_without_sufficient_history(self) -> None:
        records = [self.record(self.target - timedelta(days=index), 10_000) for index in range(1, 14)]
        anomalies = detect_anomalies(records + [self.record(self.target, 40_000)], self.target, self.config)
        self.assertEqual([], anomalies)