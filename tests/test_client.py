from __future__ import annotations

import json
import os
import unittest
from datetime import date
from unittest.mock import patch

from urllib.error import HTTPError

from usage_alert.client import HereClientError, HereUsageClient


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

    def test_fetch_bam_subscriptions_queries_the_bam_endpoint(self) -> None:
        captured_url: list[str] = []
        captured_parameters: list[dict[str, object]] = []

        def request_json(service_label: str, url: str, token: str, parameters=None) -> dict[str, object]:
            self.assertEqual("HERE BAM Customer", service_label)
            self.assertEqual("token", token)
            captured_url.append(url)
            captured_parameters.append(parameters)
            return {"subscriptions": [{"id": "SUBSCRIPTION-1", "status": "active"}]}

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
                with patch.object(client, "_request_json", side_effect=request_json):
                    subscriptions = client.fetch_bam_subscriptions()

        self.assertEqual(["https://customer.bam.api.here.com/v1/subscriptions"], captured_url)
        self.assertEqual({"offset": 0, "limit": 100}, captured_parameters[0])
        self.assertEqual("SUBSCRIPTION-1", subscriptions[0]["id"])

    def test_fetch_bam_subscription_products_queries_the_product_endpoint(self) -> None:
        captured_url: list[str] = []

        def request_json(service_label: str, url: str, token: str, parameters=None) -> dict[str, object]:
            self.assertEqual("HERE BAM Customer", service_label)
            captured_url.append(url)
            return {"items": [{"id": "PRODUCT-1", "name": "HERE SDK Explore Edition v2.0"}]}

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
                with patch.object(client, "_request_json", side_effect=request_json):
                    products = client.fetch_bam_subscription_products("SUBSCRIPTION-1")

        self.assertEqual(
            ["https://customer.bam.api.here.com/v1/subscriptions/SUBSCRIPTION-1/products"],
            captured_url,
        )
        self.assertEqual("HERE SDK Explore Edition v2.0", products[0]["name"])

    def test_fetch_app_authorization_queries_the_account_endpoint(self) -> None:
        captured_url: list[str] = []

        def request_json(service_label: str, url: str, token: str, parameters=None) -> dict[str, object]:
            self.assertEqual("HERE Account", service_label)
            captured_url.append(url)
            return {"app": {"clientId": "client-id"}, "plans": [], "policies": []}

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
                with patch.object(client, "_request_json", side_effect=request_json):
                    authorization = client.fetch_app_authorization()

        self.assertEqual(["https://account.api.here.com/app/me/authorization"], captured_url)
        self.assertEqual("client-id", authorization["app"]["clientId"])

    def test_fetch_usage_alert_rules_queries_the_usage_alert_endpoint(self) -> None:
        captured_url: list[str] = []

        def request_json(service_label: str, url: str, token: str, parameters=None) -> dict[str, object]:
            self.assertEqual("HERE Usage Alert", service_label)
            captured_url.append(url)
            return {"total": 0, "items": []}

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
                with patch.object(client, "_request_json", side_effect=request_json):
                    rules = client.fetch_usage_alert_rules()

        self.assertEqual(
            ["https://alert.usage.hereapi.com/v1/realm/realm-id/rules"],
            captured_url,
        )
        self.assertEqual([], rules["items"])

    def test_request_json_surfaces_correlation_id_and_structured_details(self) -> None:
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
            response = type(
                "Response",
                (),
                {
                    "read": lambda self: json.dumps(
                        {"code": "403403", "cause": "not authorized to perform readRules", "action": "contact support"}
                    ).encode(),
                },
            )()
            error = HTTPError("https://customer.bam.api.here.com/v1/subscriptions", 403, "Forbidden", None, response)
            error.headers = {"X-Correlation-ID": "correlation-1"}
            with patch.object(client, "_access_token", return_value="token"):
                with self.assertRaises(HereClientError) as raised:
                    with patch("usage_alert.client.urlopen", side_effect=error):
                        client.fetch_bam_subscriptions()
        self.assertIn("cause=not authorized to perform readRules", str(raised.exception))
        self.assertIn("correlation ID: correlation-1", str(raised.exception))

    def test_realm_id_is_auto_discovered_from_app_authorization_when_not_configured(self) -> None:
        captured: list[tuple[str, str]] = []

        def request_json(service_label: str, url: str, token: str, parameters=None) -> dict[str, object]:
            captured.append((service_label, url))
            return {"app": {"clientId": "shared-app", "realm": "org-discovered"}}

        with patch.dict(
            os.environ,
            {
                "HERE_REALM_ID": "",
                "here.access.key.id": "client-id",
                "here.access.key.secret": "client-secret",
                "here.client.id": "shared-app",
            },
            clear=False,
        ):
            client = HereUsageClient()
            self.assertIsNone(client._realm_id)
            with patch.object(client, "_access_token", return_value="token"):
                with patch.object(client, "_request_json", side_effect=request_json):
                    self.assertEqual("org-discovered", client.realm_id)
            self.assertEqual("org-discovered", client.realm_id)

        self.assertEqual([("HERE Account", "https://account.api.here.com/app/me/authorization")], captured)

    def test_realm_discovery_rejects_mismatched_app_client_id(self) -> None:
        with patch.dict(
            os.environ,
            {
                "HERE_REALM_ID": "",
                "here.access.key.id": "client-id",
                "here.access.key.secret": "client-secret",
                "here.client.id": "expected-app",
            },
            clear=False,
        ):
            client = HereUsageClient()
            with patch.object(client, "_access_token", return_value="token"):
                with patch.object(
                    client,
                    "_request_json",
                    return_value={"app": {"clientId": "actual-app", "realm": "org-x"}},
                ):
                    with self.assertRaises(HereClientError) as raised:
                        _ = client.realm_id
        self.assertIn(
            "Configured app client id expected-app does not match the credential's app actual-app",
            str(raised.exception),
        )

    def test_client_accepts_lowercase_dotted_credential_keys(self) -> None:
        with patch.dict(
            os.environ,
            {
                "HERE_REALM_ID": "realm-id",
                "HERE_MONITOR_ACCESS_KEY_ID": "",
                "HERE_MONITOR_ACCESS_KEY_SECRET": "",
                "here.access.key.id": "lower-key-id",
                "here.access.key.secret": "lower-key-secret",
                "here.client.id": "lower-app-client",
            },
            clear=False,
        ):
            client = HereUsageClient()
        self.assertEqual("lower-key-id", client.client_id)
        self.assertEqual("lower-key-secret", client.client_secret)
        self.assertEqual("lower-app-client", client.app_client_id)
        self.assertEqual("realm-id", client.realm_id)

    def test_lowercase_canonical_names_take_precedence_over_legacy_here_forms(self) -> None:
        with patch.dict(
            os.environ,
            {
                "HERE_REALM_ID": "legacy-realm",
                "HERE_MONITOR_ACCESS_KEY_ID": "legacy-key-id",
                "HERE_MONITOR_ACCESS_KEY_SECRET": "legacy-key-secret",
                "here.access.key.id": "canonical-key-id",
                "here.access.key.secret": "canonical-key-secret",
                "here.client.id": "canonical-app-client",
                "HERE_CLIENT_ID": "legacy-app-client",
            },
            clear=False,
        ):
            client = HereUsageClient()
        self.assertEqual("canonical-key-id", client.client_id)
        self.assertEqual("canonical-key-secret", client.client_secret)
        self.assertEqual("canonical-app-client", client.app_client_id)
        self.assertEqual("legacy-realm", client.realm_id)

    def test_legacy_here_credential_forms_still_work_as_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {
                "HERE_REALM_ID": "legacy-realm",
                "HERE_MONITOR_ACCESS_KEY_ID": "legacy-key-id",
                "HERE_MONITOR_ACCESS_KEY_SECRET": "legacy-key-secret",
                "here.access.key.id": "",
                "here.access.key.secret": "",
            },
            clear=False,
        ):
            client = HereUsageClient()
        self.assertEqual("legacy-key-id", client.client_id)
        self.assertEqual("legacy-key-secret", client.client_secret)
        self.assertEqual("", client.app_client_id)


if __name__ == "__main__":
    unittest.main()