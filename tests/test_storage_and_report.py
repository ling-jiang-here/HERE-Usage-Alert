from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from usage_alert.models import UsageRecord
from usage_alert.report import render_daily_report
from usage_alert.storage import read_records, write_daily_records


class StorageAndReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = UsageRecord(
            date(2026, 8, 18), "transactions", 12_500, "transactions", "routing", "fleet-prod",
            None, None, '{"app_id":"fleet-prod","feature_id":"routing"}', datetime.now(timezone.utc),
        )

    def test_daily_write_is_idempotent_and_readable(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            first_path = write_daily_records([self.record], directory)
            second_path = write_daily_records([self.record], directory)
            self.assertEqual(first_path, second_path)
            self.assertEqual([self.record], read_records(directory))

    def test_no_anomaly_report_is_explicit(self) -> None:
        self.assertIn("No anomaly met", render_daily_report([self.record], []))