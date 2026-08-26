from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from usage_alert.main import main
from usage_alert.models import UsageRecord
from usage_alert.storage import write_hourly_records


class MainTests(unittest.TestCase):
    def test_fetch_mode_persists_local_analysis_files_and_prunes_old_ones(self) -> None:
        target_date = date(2026, 8, 18)
        payload = {
            "items": [
                {
                    "usage_date_utc": target_date.isoformat(),
                    "metric": "transactions",
                    "quantity": 10_000,
                    "unit": "Transactions",
                    "feature_id": "routing",
                    "app_id": "fleet-prod",
                }
            ]
        }
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "config").mkdir()
            (root / "data" / "curated").mkdir(parents=True)
            (root / "reports").mkdir(parents=True)
            (root / "data" / "curated" / "2026-05-19.csv").write_text("stale", encoding="utf-8")
            (root / "data" / "curated" / "2026-07-05.csv").write_text("recent-enough", encoding="utf-8")
            (root / "reports" / "2026-05-19.md").write_text("stale", encoding="utf-8")
            (root / "reports" / "2026-06-25.md").write_text("within-retention", encoding="utf-8")
            (root / "config" / "thresholds.json").write_text(
                json.dumps(
                    {
                        "history_days": 30,
                        "data_retention_days": 45,
                        "report_retention_days": 60,
                        "minimum_baseline_days": 14,
                        "minimum_absolute_increase": 1000,
                        "percentage_increase_threshold": 0.5,
                        "robust_z_score_threshold": 3.5,
                        "severity": {"warning_percentage": 0.5, "critical_percentage": 2.0},
                    }
                ),
                encoding="utf-8",
            )
            (root / "config" / "free_tiers.json").write_text(
                json.dumps(
                    {
                        "approaching_threshold": 0.8,
                        "data_io_free_gb_months": 20,
                        "transaction_free_tiers": {"transactions": 300_000},
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "HERE_USAGE_API_BASE_URL": "https://example.test/v2",
                    "HERE_REALM_ID": "example",
                    "HERE_USAGE_API_CLIENT_ID": "client-id",
                    "HERE_USAGE_API_CLIENT_SECRET": "client-secret",
                    "HERE_USAGE_API_USAGE_PATH": "/usage/realms/{realmId}",
                },
                clear=False,
            ):
                with patch("usage_alert.main.HereUsageClient.fetch_usage", return_value=json.dumps(payload)):
                    with patch("usage_alert.main.notify_webhook") as notify_webhook:
                        with patch(
                            "sys.argv",
                            [
                                "usage_alert.main",
                                "--fetch",
                                "--date",
                                target_date.isoformat(),
                                "--root",
                                str(root),
                            ],
                        ):
                            self.assertEqual(0, main())
            self.assertTrue((root / "data" / "curated" / "2026-08-18.csv").exists())
            self.assertTrue((root / "reports" / "2026-08-18.md").exists())
            self.assertFalse((root / "data" / "curated" / "2026-05-19.csv").exists())
            self.assertTrue((root / "data" / "curated" / "2026-07-05.csv").exists())
            self.assertFalse((root / "reports" / "2026-05-19.md").exists())
            self.assertTrue((root / "reports" / "2026-06-25.md").exists())
            self.assertFalse((root / "artifacts").exists())
            notify_webhook.assert_not_called()

    def test_hourly_fetch_mode_skips_empty_completed_hour(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "config").mkdir()
            (root / "config" / "thresholds.json").write_text(
                json.dumps(
                    {
                        "history_days": 30,
                        "data_retention_days": 45,
                        "report_retention_days": 60,
                        "minimum_baseline_days": 14,
                        "minimum_absolute_increase": 1000,
                        "percentage_increase_threshold": 0.5,
                        "robust_z_score_threshold": 3.5,
                        "severity": {"warning_percentage": 0.5, "critical_percentage": 2.0},
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "HERE_USAGE_API_BASE_URL": "https://example.test/v2",
                    "HERE_REALM_ID": "example",
                    "HERE_USAGE_API_CLIENT_ID": "client-id",
                    "HERE_USAGE_API_CLIENT_SECRET": "client-secret",
                    "HERE_USAGE_API_USAGE_PATH": "/usage/realms/{realmId}",
                },
                clear=False,
            ):
                with patch("usage_alert.main.HereUsageClient.fetch_usage_hour", return_value=json.dumps({"items": []})):
                    with patch("usage_alert.main.notify_webhook") as notify_webhook:
                        with patch(
                            "sys.argv",
                            [
                                "usage_alert.main",
                                "--fetch",
                                "--hourly",
                                "--root",
                                str(root),
                            ],
                        ):
                            self.assertEqual(0, main())
            self.assertFalse((root / "data").exists())
            self.assertFalse((root / "reports").exists())
            notify_webhook.assert_not_called()

    def test_hourly_fetch_mode_alerts_for_zero_free_tier_usage(self) -> None:
        target_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        payload = {
            "items": [
                {
                    "usageDateTime": target_hour.isoformat().replace("+00:00", "Z"),
                    "name": "Fuel Prices",
                    "billableValue": 5,
                    "valueDriver": "Transactions",
                    "featureId": "fuel-prices",
                    "appId": "fleet-prod",
                }
            ]
        }
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "config").mkdir()
            (root / "config" / "thresholds.json").write_text(
                json.dumps(
                    {
                        "history_days": 30,
                        "data_retention_days": 45,
                        "report_retention_days": 60,
                        "minimum_baseline_days": 14,
                        "minimum_absolute_increase": 1000,
                        "percentage_increase_threshold": 0.5,
                        "robust_z_score_threshold": 3.5,
                        "severity": {"warning_percentage": 0.5, "critical_percentage": 2.0},
                    }
                ),
                encoding="utf-8",
            )
            (root / "config" / "free_tiers.json").write_text(
                json.dumps(
                    {
                        "approaching_threshold": 0.8,
                        "data_io_free_gb_months": 20,
                        "transaction_free_tiers": {"Fuel Prices": 0},
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "HERE_USAGE_API_BASE_URL": "https://example.test/v2",
                    "HERE_REALM_ID": "example",
                    "HERE_USAGE_API_CLIENT_ID": "client-id",
                    "HERE_USAGE_API_CLIENT_SECRET": "client-secret",
                    "HERE_USAGE_API_USAGE_PATH": "/usage/realms/{realmId}",
                },
                clear=False,
            ):
                with patch("usage_alert.main.HereUsageClient.fetch_usage_hour", return_value=json.dumps(payload)):
                    with patch("usage_alert.main.notify_webhook") as notify_webhook:
                        with patch(
                            "sys.argv",
                            [
                                "usage_alert.main",
                                "--fetch",
                                "--hourly",
                                "--root",
                                str(root),
                            ],
                        ):
                            self.assertEqual(0, main())
            self.assertTrue((root / "data" / "hourly" / f"{target_hour.strftime('%Y-%m-%dT%H')}Z.csv").exists())
            self.assertTrue((root / "reports" / "hourly" / f"{target_hour.strftime('%Y-%m-%dT%H')}Z.md").exists())
            notify_webhook.assert_called_once()

    def test_hourly_fetch_mode_alerts_when_month_to_date_usage_exceeds_nonzero_free_tier(self) -> None:
        target_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        payload = {
            "items": [
                {
                    "usageDateTime": target_hour.isoformat().replace("+00:00", "Z"),
                    "name": "Autocomplete",
                    "billableValue": 1,
                    "valueDriver": "Transactions",
                    "featureId": "autocomplete",
                    "appId": "fleet-prod",
                }
            ]
        }
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "config").mkdir()
            (root / "data" / "hourly").mkdir(parents=True)
            (root / "config" / "thresholds.json").write_text(
                json.dumps(
                    {
                        "history_days": 30,
                        "data_retention_days": 45,
                        "report_retention_days": 60,
                        "minimum_baseline_days": 14,
                        "minimum_absolute_increase": 1000,
                        "percentage_increase_threshold": 0.5,
                        "robust_z_score_threshold": 3.5,
                        "severity": {"warning_percentage": 0.5, "critical_percentage": 2.0},
                    }
                ),
                encoding="utf-8",
            )
            (root / "config" / "free_tiers.json").write_text(
                json.dumps(
                    {
                        "approaching_threshold": 0.8,
                        "data_io_free_gb_months": 20,
                        "transaction_free_tiers": {"Autocomplete": 30_000},
                    }
                ),
                encoding="utf-8",
            )
            prior_hour = target_hour - timedelta(hours=1)
            write_hourly_records(
                [
                    UsageRecord(
                        usage_date=prior_hour.date(),
                        metric="Autocomplete",
                        quantity=30_000,
                        unit="Transactions",
                        feature_id="autocomplete",
                        app_id="fleet-prod",
                        project_id=None,
                        billing_tag=None,
                        dimension_key='{"app_id":"fleet-prod","feature_id":"autocomplete"}',
                        source_retrieved_at=prior_hour,
                        usage_hour_utc=prior_hour,
                    )
                ],
                root / "data" / "hourly",
            )
            with patch.dict(
                os.environ,
                {
                    "HERE_USAGE_API_BASE_URL": "https://example.test/v2",
                    "HERE_REALM_ID": "example",
                    "HERE_USAGE_API_CLIENT_ID": "client-id",
                    "HERE_USAGE_API_CLIENT_SECRET": "client-secret",
                    "HERE_USAGE_API_USAGE_PATH": "/usage/realms/{realmId}",
                },
                clear=False,
            ):
                with patch("usage_alert.main.HereUsageClient.fetch_usage_hour", return_value=json.dumps(payload)):
                    with patch("usage_alert.main.notify_webhook") as notify_webhook:
                        with patch(
                            "sys.argv",
                            [
                                "usage_alert.main",
                                "--fetch",
                                "--hourly",
                                "--root",
                                str(root),
                            ],
                        ):
                            self.assertEqual(0, main())
            self.assertTrue((root / "reports" / "hourly" / f"{target_hour.strftime('%Y-%m-%dT%H')}Z.md").exists())
            notify_webhook.assert_called_once()