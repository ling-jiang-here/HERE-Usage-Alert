from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from usage_alert.models import UsageRecord
from usage_alert.rules import (
    SavedUsageAlertRules,
    UsageAlertRule,
    UsageThresholdCondition,
    evaluate_usage_alert_rules,
    parse_usage_alert_rules,
    synthetic_usage_record_for_rule,
)
from usage_alert.storage import read_usage_alert_rules_file, write_usage_alert_rules_file

RULES_PAYLOAD = {
    "total": 2,
    "limit": 100,
    "items": [
        {
            "id": "UsageAlertRule-1",
            "name": "Alert for App Id and auto suggest one",
            "description": "descr",
            "queryConditions": [
                {"key": "featureId", "value": "hrn:here:service::org-1:search-autosuggest-7"},
                {"key": "appId", "value": "app-1"},
                {"key": "realm", "value": "org-1"},
            ],
            "usageThresholdConditions": [
                {"thresholdType": "absolute", "threshold": 20, "actions": ["alert"]}
            ],
            "timeRange": {"duration": "daily"},
            "status": "active",
            "emailNotifications": ["a@b.com"],
            "webhookUrl": "https://webhook.site/x",
        },
        {
            "id": "UsageAlertRule-2",
            "name": "Inactive rule",
            "description": "descr",
            "queryConditions": [{"key": "appId", "value": "app-2"}],
            "usageThresholdConditions": [
                {"thresholdType": "absolute", "threshold": 5, "actions": ["alert"]}
            ],
            "timeRange": {"duration": "daily"},
            "status": "disabled",
            "emailNotifications": [],
        },
    ],
}


def _record(
    metric: str = "transactions",
    quantity: float = 10.0,
    feature_id: str | None = "hrn:here:service::org-1:search-autosuggest-7",
    app_id: str | None = "app-1",
) -> UsageRecord:
    return UsageRecord(
        usage_date=date(2026, 9, 1),
        metric=metric,
        quantity=quantity,
        unit="Transactions",
        feature_id=feature_id,
        app_id=app_id,
        project_id=None,
        billing_tag=None,
        dimension_key='{"app_id":"app-1","feature_id":"hrn:here:service::org-1:search-autosuggest-7"}',
        source_retrieved_at=datetime.now(timezone.utc),
        category=None,
        usage_hour_utc=None,
    )


class RuleParsingTests(unittest.TestCase):
    def test_parse_usage_alert_rules_builds_validated_rules(self) -> None:
        rules = parse_usage_alert_rules(RULES_PAYLOAD)
        self.assertEqual(2, len(rules))
        first = rules[0]
        self.assertEqual("UsageAlertRule-1", first.id)
        self.assertEqual("Alert for App Id and auto suggest one", first.name)
        self.assertEqual(3, len(first.query_conditions))
        self.assertEqual("realm", first.query_conditions[2].key)
        self.assertEqual(20.0, first.absolute_threshold)
        self.assertTrue(first.is_active)
        self.assertEqual("daily", first.time_range_duration)
        self.assertEqual(("a@b.com",), first.email_notifications)
        self.assertEqual("https://webhook.site/x", first.webhook_url)
        self.assertFalse(rules[1].is_active)

    def test_parse_usage_alert_rules_requires_items_list(self) -> None:
        with self.assertRaises(ValueError):
            parse_usage_alert_rules({"total": 0})
        with self.assertRaises(ValueError):
            parse_usage_alert_rules({"items": [{"id": 1}]})

    def test_rule_matches_record_by_query_conditions(self) -> None:
        rule = parse_usage_alert_rules(RULES_PAYLOAD)[0]
        self.assertTrue(rule.matches_record(_record()))
        self.assertFalse(rule.matches_record(_record(app_id="other-app")))
        self.assertFalse(rule.matches_record(_record(feature_id="hrn:here:service::org-1:routing")))

    def test_rule_without_absolute_threshold_has_none(self) -> None:
        from usage_alert.rules import UsageAlertRule

        rule = UsageAlertRule(
            id="r", name="n", description="d",
            threshold_conditions=(), status="active", time_range_duration="daily",
        )
        self.assertIsNone(rule.absolute_threshold)


class RuleEvaluationTests(unittest.TestCase):
    def test_evaluate_flags_matched_rule_crossing_threshold(self) -> None:
        rule = parse_usage_alert_rules(RULES_PAYLOAD)[0]
        alerts = evaluate_usage_alert_rules([_record(quantity=25)], [rule])
        self.assertEqual(1, len(alerts))
        self.assertEqual(rule, alerts[0].rule)
        self.assertEqual(25.0, alerts[0].observed)
        self.assertEqual(20.0, alerts[0].threshold)
        self.assertEqual(5.0, alerts[0].exceeded_by)

    def test_evaluate_skips_rule_below_threshold(self) -> None:
        rule = parse_usage_alert_rules(RULES_PAYLOAD)[0]
        self.assertEqual([], evaluate_usage_alert_rules([_record(quantity=5)], [rule]))

    def test_evaluate_skips_inactive_rules(self) -> None:
        rules = parse_usage_alert_rules(RULES_PAYLOAD)
        inactive = rules[1]
        self.assertFalse(inactive.is_active)
        matching_record = _record(app_id="app-2")
        self.assertEqual([], evaluate_usage_alert_rules([matching_record], [inactive]))

    def test_evaluate_skips_rules_with_non_daily_time_ranges(self) -> None:
        hourly_rule = UsageAlertRule(
            id="r",
            name="n",
            description="d",
            query_conditions=(),
            threshold_conditions=(UsageThresholdCondition("absolute", 5.0, ("alert",)),),
            time_range_duration="hourly",
            status="active",
        )
        self.assertEqual([], evaluate_usage_alert_rules([_record(quantity=100)], [hourly_rule]))

    def test_evaluate_sums_all_matching_series_and_uses_apex_unit(self) -> None:
        rule = parse_usage_alert_rules(RULES_PAYLOAD)[0]
        alerts = evaluate_usage_alert_rules(
            [_record(metric="autocomplete", quantity=12), _record(metric="suggest", quantity=9)], [rule]
        )
        self.assertEqual(1, len(alerts))
        self.assertEqual(21.0, alerts[0].observed)

    def test_evaluate_ignores_unknown_query_keys_like_realm(self) -> None:
        rule = parse_usage_alert_rules(RULES_PAYLOAD)[0]
        alerts = evaluate_usage_alert_rules([_record(quantity=30)], [rule])
        self.assertEqual(1, len(alerts))

    def test_synthetic_record_crosses_rule_threshold(self) -> None:
        rule = parse_usage_alert_rules(RULES_PAYLOAD)[0]
        record = synthetic_usage_record_for_rule(rule, date(2026, 9, 1))
        self.assertEqual("app-1", record.app_id)
        self.assertEqual("hrn:here:service::org-1:search-autosuggest-7", record.feature_id)
        self.assertEqual(21.0, record.quantity)
        alerts = evaluate_usage_alert_rules([record], [rule])
        self.assertEqual(1, len(alerts))


class RuleStorageTests(unittest.TestCase):
    def test_saved_rules_round_trip_through_json_file(self) -> None:
        rules = parse_usage_alert_rules(RULES_PAYLOAD)
        saved = SavedUsageAlertRules(datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc), tuple(rules))
        with TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "data" / "usage-alert-rules.json"
            write_usage_alert_rules_file(saved, path)
            self.assertTrue(path.exists())
            restored = read_usage_alert_rules_file(path)
        self.assertIsNotNone(restored)
        self.assertEqual(2, len(restored.rules))
        self.assertEqual("UsageAlertRule-1", restored.rules[0].id)
        self.assertEqual("https://webhook.site/x", restored.rules[0].webhook_url)
        self.assertEqual("2026-09-06T12:00:00+00:00", restored.retrieved_at_utc.isoformat())

    def test_read_usage_alert_rules_missing_or_corrupt_file_returns_none(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "usage-alert-rules.json"
            self.assertIsNone(read_usage_alert_rules_file(missing))
            corrupt = Path(temporary_directory) / "corrupt.json"
            corrupt.write_text("{not json", encoding="utf-8")
            self.assertIsNone(read_usage_alert_rules_file(corrupt))


if __name__ == "__main__":
    unittest.main()