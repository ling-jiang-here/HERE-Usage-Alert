from datetime import date, datetime, timezone
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from usage_alert.models import Anomaly, UsageRecord
from usage_alert.notify import build_healthy_webhook_payload, build_quota_alert_payload, build_webhook_payload, notify_webhook
from usage_alert.quota import QuotaStatus


class NotificationTests(unittest.TestCase):
    def test_notifier_includes_application_user_agent(self) -> None:
        record = UsageRecord(
            date(2026, 8, 18), "transactions", 40_000, "transactions", "routing", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"routing"}', datetime.now(timezone.utc),
        )
        anomaly = Anomaly(record, 10_000, 14, 30_000, 3.0, None, "critical")
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with patch.dict(os.environ, {"ALERT_WEBHOOK_URL": "https://example.test/webhook"}, clear=False):
            with patch("usage_alert.notify.urlopen", return_value=response) as urlopen:
                self.assertTrue(notify_webhook([anomaly], [record], "reports/2026-08-18.md"))

        request = urlopen.call_args.args[0]
        self.assertEqual("HERE-Usage-Alert/0.1", request.get_header("User-agent"))

    def test_payload_contains_alert_evidence_without_secrets(self) -> None:
        record = UsageRecord(
            date(2026, 8, 18), "transactions", 40_000, "transactions", "routing", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"routing"}', datetime.now(timezone.utc),
        )
        anomaly = Anomaly(record, 10_000, 14, 30_000, 3.0, None, "critical")
        payload = build_webhook_payload([anomaly], "reports/2026-08-18.md")
        self.assertEqual("here_usage_alert", payload["event"])
        self.assertEqual("critical", payload["severity"])
        self.assertEqual(40_000, payload["anomalies"][0]["observed_quantity"])

    def test_quota_alert_payload_includes_exceeded_services(self) -> None:
        record = UsageRecord(
            date(2026, 8, 18), "Fuel Prices", 1, "Transactions", "fuel-prices", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"fuel-prices"}', datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 1, 0, None, "EXCEEDED")
        payload = build_quota_alert_payload([record], [quota], "reports/2026-08-18.md")
        self.assertEqual("here_usage_alert", payload["event"])
        self.assertEqual(1, payload["quota_alert_count"])
        self.assertEqual("Fuel Prices", payload["quota_alerts"][0]["metric"])
        self.assertIsNone(payload["quota_alerts"][0]["percentage"])
        json.dumps(payload, allow_nan=False)

    def test_quota_alert_payload_includes_remediation_advisory(self) -> None:
        record = UsageRecord(
            date(2026, 8, 18), "Fuel Prices", 1, "Transactions", "fuel-prices", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"fuel-prices"}', datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 1, 0, None, "EXCEEDED")
        payload = build_quota_alert_payload(
            [record], [quota], "reports/2026-08-18.md",
            "The monitor is using credentials from this same app. Separate the monitor credential.",
        )
        self.assertIn("Separate the monitor credential", payload["note"])

    def test_quota_alert_payload_sanitizes_non_finite_percentage(self) -> None:
        record = UsageRecord(
            date(2026, 8, 18), "Fuel Prices", 1, "Transactions", "fuel-prices", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"fuel-prices"}', datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 1, 0, float("inf"), "EXCEEDED")
        payload = build_quota_alert_payload([record], [quota], "reports/2026-08-18.md")
        self.assertIsNone(payload["quota_alerts"][0]["percentage"])
        json.dumps(payload, allow_nan=False)

    def test_healthy_payload_confirms_successful_no_anomaly_run(self) -> None:
        record = UsageRecord(
            date(2026, 8, 18), "transactions", 12_500, "transactions", "routing", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"routing"}', datetime.now(timezone.utc),
        )
        payload = build_healthy_webhook_payload([record], "reports/2026-08-18.md")
        self.assertEqual("here_usage_healthy", payload["event"])
        self.assertEqual("info", payload["severity"])
        self.assertEqual(0, payload["anomaly_count"])
        self.assertEqual(
            [{"unit": "transactions", "metric": "transactions", "quantity": 12_500}],
            payload["usage_summary"],
        )