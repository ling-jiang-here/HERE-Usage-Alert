from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import patch

from usage_alert.client import HereUsageClient


class HereUsageClientTests(unittest.TestCase):
    def test_fetch_usage_queries_the_requested_utc_day(self) -> None:
        captured_parameters: dict[str, object] = {}

        def request_usage(_url: str, _token: str, parameters: dict[str, object]) -> dict[str, object]:
            captured_parameters.update(parameters)
            return {"items": []}

        with patch.dict(
            os.environ,
            {
                "HERE_REALM_ID": "realm-id",
                "HERE_MONITOR_ACCESS_KEY_ID": "client-id",
                "HERE_MONITOR_ACCESS_KEY_SECRET": "client-secret",
            },
            clear=False,
        ):
            client = HereUsageClient()
            with patch.object(client, "_access_token", return_value="token"):
                with patch.object(client, "_request_usage", side_effect=request_usage):
                    client.fetch_usage(date(2026, 8, 30))

        self.assertEqual("2026-08-30T00:00:00Z", captured_parameters["startDate"])
        self.assertEqual("2026-08-30T23:59:59Z", captured_parameters["endDate"])
        self.assertEqual("day", captured_parameters["detailLevel"])


if __name__ == "__main__":
    unittest.main()