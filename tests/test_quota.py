from dataclasses import replace
from datetime import date, datetime, timezone
import unittest

from usage_alert.models import UsageRecord
from usage_alert.quota import evaluate_month_to_date


def record(metric: str, quantity: float, unit: str = "Transactions") -> UsageRecord:
    return UsageRecord(
        date(2026, 8, 18), metric, quantity, unit, metric, "example-app", None, None,
        '{"app_id":"example-app"}', datetime.now(timezone.utc),
    )


class QuotaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.free_tiers = {"Autocomplete": 30_000, "Discover / Search": 5_000}

    def test_classifies_within_approaching_and_exceeded_services(self) -> None:
        statuses = evaluate_month_to_date(
            [record("Autocomplete", 24_000), record("Discover / Search", 5_001)],
            0.8,
            self.free_tiers,
            20,
        )
        self.assertEqual(["APPROACHING", "EXCEEDED"], [status.status for status in statuses[:2]])

    def test_ignores_incompatible_units_and_unconfigured_services(self) -> None:
        statuses = evaluate_month_to_date(
            [record("Autocomplete", 30_000, "GB-Months"), record("Unmapped", 10)],
            0.8,
            self.free_tiers,
            20,
        )
        self.assertEqual(["Data IO total"], [status.metric for status in statuses])
        self.assertEqual("NOT_REPORTED", statuses[0].status)

    def test_evaluates_data_io_gb_only_when_here_reports_data_io_category(self) -> None:
        data_io_record = record("Data IO", 16)
        data_io_record = replace(data_io_record, category="DataStorage", unit="GB-Months")
        statuses = evaluate_month_to_date([data_io_record], 0.8, self.free_tiers, 20)
        self.assertEqual("APPROACHING", statuses[-1].status)

    def test_excludes_data_io_throughput_without_a_matching_allowance(self) -> None:
        throughput_record = replace(record("Data IO", 0.0312), category="DataStorage", unit="MB/S-Months")
        statuses = evaluate_month_to_date([throughput_record], 0.8, self.free_tiers, 20)
        self.assertEqual(1, len(statuses))
        self.assertEqual("NOT_REPORTED", statuses[0].status)

    def test_sums_data_storage_records_within_the_same_unit(self) -> None:
        first = replace(record("Data IO", 7), category="DataStorage", unit="GB-Months")
        second = replace(record("Data IO", 9), category="DataStorage", unit="GB-Months")
        statuses = evaluate_month_to_date([first, second], 0.8, self.free_tiers, 20)
        self.assertEqual(16, statuses[-1].usage)
        self.assertEqual("APPROACHING", statuses[-1].status)