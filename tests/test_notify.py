from datetime import date, datetime, timezone
import unittest

from usage_alert.models import Anomaly, UsageRecord
from usage_alert.notify import build_webhook_payload


class NotificationTests(unittest.TestCase):
    def test_payload_contains_alert_evidence_without_secrets(self) -> None:
        record = UsageRecord(
            date(2026, 8, 18), "transactions", 40_000, "transactions", "routing", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"routing"}', datetime.now(timezone.utc),
        )
        anomaly = Anomaly(record, 10_000, 14, 30_000, 3.0, None, "critical")
        payload = build_webhook_payload([anomaly], "reports/2026-08-18.md")
        self.assertEqual("here_usage_anomaly", payload["event"])
        self.assertEqual("critical", payload["severity"])
        self.assertEqual(40_000, payload["anomalies"][0]["observed_quantity"])