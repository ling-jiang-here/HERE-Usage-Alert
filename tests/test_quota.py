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
        )
        self.assertEqual(["APPROACHING", "EXCEEDED"], [status.status for status in statuses])

    def test_ignores_incompatible_units_and_unconfigured_services(self) -> None:
        statuses = evaluate_month_to_date(
            [record("Autocomplete", 30_000, "GB-Months"), record("Unmapped", 10)],
            0.8,
            self.free_tiers,
        )
        self.assertEqual([], statuses)