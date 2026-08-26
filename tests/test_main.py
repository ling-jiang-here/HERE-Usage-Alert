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
    def test_fetch_mode_keeps_reports_and_data_in_memory(self) -> None:
        target_date = date(2026, 8, 18)
        payload = {
            "items": [
                {
                    "usage_date_utc": (target_date - timedelta(days=offset)).isoformat(),
                    "metric": "transactions",
                    "quantity": 10_000,
                    "unit": "Transactions",
                    "feature_id": "routing",
                    "app_id": "fleet-prod",
                }
                for offset in range(14, -1, -1)
            ]
        }
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "config").mkdir()
            (root / "config" / "thresholds.json").write_text(
                json.dumps(
                    {
                        "history_days": 30,
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
                with patch("usage_alert.main.HereUsageClient.fetch_usage_range", return_value=json.dumps(payload)):
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
            self.assertFalse((root / "data").exists())
            self.assertFalse((root / "reports").exists())
            self.assertFalse((root / "artifacts").exists())
            notify_webhook.assert_not_called()