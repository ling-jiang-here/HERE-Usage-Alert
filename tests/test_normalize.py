from datetime import datetime, timezone
import unittest

from usage_alert.normalize import SchemaError, normalize_records


class NormalizeTests(unittest.TestCase):
    def test_normalizes_dimensions_into_a_stable_key(self) -> None:
        records = normalize_records([{
            "usage_date_utc": "2026-08-18", "metric": "transactions", "quantity": 2,
            "unit": "transactions", "feature_id": "routing", "app_id": "fleet-prod",
        }], datetime(2026, 8, 19, tzinfo=timezone.utc))
        self.assertEqual('{"app_id":"fleet-prod","feature_id":"routing"}', records[0].dimension_key)

    def test_rejects_negative_quantities(self) -> None:
        with self.assertRaises(SchemaError):
            normalize_records([{
                "usage_date_utc": "2026-08-18", "metric": "transactions", "quantity": -1,
                "unit": "transactions",
            }])

    def test_normalizes_documented_here_usage_item(self) -> None:
        records = normalize_records({"items": [{
            "usageDateTime": "2026-08-18T00:00:00", "name": "Routing", "usageValue": "125000",
            "valueDriver": "Transactions", "featureId": "routing", "appId": "fleet-prod",
            "projectHrn": "hrn:here:authorization::org:project/fleet", "billingTag": "production",
        }]})
        self.assertEqual("Routing", records[0].metric)
        self.assertEqual(125000, records[0].quantity)
        self.assertEqual("fleet-prod", records[0].app_id)