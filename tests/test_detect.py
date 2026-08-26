from datetime import date, datetime, timedelta, timezone
import unittest

from usage_alert.detect import detect_anomalies, detect_hourly_anomalies
from usage_alert.models import DetectionConfig, UsageRecord


class DetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = DetectionConfig(30, 14, 1000, 0.5, 3.5, 0.5, 2.0)
        self.target = date(2026, 8, 18)

    def record(self, usage_date: date, quantity: float, usage_hour=None) -> UsageRecord:
        return UsageRecord(
            usage_date, "transactions", quantity, "transactions", "routing", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"routing"}',
            datetime.now(timezone.utc),
            usage_hour_utc=usage_hour,
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

    def test_flags_spike_for_same_hour_on_prior_days(self) -> None:
        target_hour = datetime(2026, 8, 18, 10, tzinfo=timezone.utc)
        history = [
            self.record(
                target_hour.date() - timedelta(days=index), 10_000,
                target_hour - timedelta(days=index),
            )
            for index in range(1, 15)
        ]
        current = self.record(target_hour.date(), 40_000, target_hour)
        anomalies = detect_hourly_anomalies(history + [current], target_hour, self.config)
        self.assertEqual(1, len(anomalies))