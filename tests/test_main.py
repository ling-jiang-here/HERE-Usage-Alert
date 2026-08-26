from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from usage_alert.main import main


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