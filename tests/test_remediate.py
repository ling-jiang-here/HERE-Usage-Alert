from __future__ import annotations

import os
import unittest
from datetime import date, datetime, timezone
from unittest.mock import Mock

from usage_alert.models import UsageRecord
from usage_alert.quota import QuotaStatus
from usage_alert.client import HereClientError
from usage_alert.remediate import (
    maybe_disable_app_credentials,
    maybe_limit_app_to_within_free_tier_project,
    maybe_remediate_app_access,
    _managed_project_id,
)


class RemediationTests(unittest.TestCase):
    def test_disables_all_credentials_for_implicated_app_when_service_is_exceeded(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="fuel-prices",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_apps.return_value = [{"id": "target-app", "hrn": "hrn:app/target-app"}]
        identity_client.list_api_keys.return_value = [
            {"apiKey": "hrn:apikey/1", "apiKeyId": "api-key-1", "enabled": True},
            {"apiKey": "hrn:apikey/2", "apiKeyId": "api-key-2", "enabled": True},
        ]
        identity_client.list_access_keys.return_value = [{"accessKeyHrn": "hrn:accesskey/1", "accessKeyId": "client-id-1", "enabled": True}]

        with unittest.mock.patch.dict(
            os.environ,
            {
                "HERE_AUTO_DISABLE_APP_CREDENTIALS": "true",
                "HERE_MONITOR_ACCESS_KEY_ID": "monitor-client-id",
            },
            clear=False,
        ):
            result = maybe_disable_app_credentials([record], [quota], identity_client)

        self.assertTrue(result.triggered)
        self.assertTrue(result.api_key_disabled)
        self.assertTrue(result.oauth_credentials_disabled)
        self.assertEqual(
            [
                unittest.mock.call("hrn:app/target-app", "hrn:apikey/1"),
                unittest.mock.call("hrn:app/target-app", "hrn:apikey/2"),
            ],
            identity_client.disable_api_key.call_args_list,
        )
        identity_client.disable_access_key.assert_called_once_with("hrn:app/target-app", "hrn:accesskey/1")

    def test_skips_when_toggle_disabled(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="fuel-prices",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()

        with unittest.mock.patch.dict(os.environ, {"HERE_AUTO_DISABLE_APP_CREDENTIALS": "false"}, clear=False):
            result = maybe_disable_app_credentials([record], [quota], identity_client)

        self.assertFalse(result.triggered)
        identity_client.disable_api_key.assert_not_called()

    def test_skips_api_keys_when_not_discoverable_but_disables_oauth_access_keys(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="fuel-prices",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_apps.return_value = [{"id": "target-app", "hrn": "hrn:app/target-app"}]
        identity_client.list_api_keys.return_value = []
        identity_client.list_access_keys.return_value = [{"accessKeyHrn": "hrn:accesskey/1", "accessKeyId": "client-id-1", "enabled": True}]

        with unittest.mock.patch.dict(
            os.environ,
            {
                "HERE_AUTO_DISABLE_APP_CREDENTIALS": "true",
                "HERE_MONITOR_ACCESS_KEY_ID": "monitor-client-id",
            },
            clear=False,
        ):
            result = maybe_disable_app_credentials([record], [quota], identity_client)

        self.assertTrue(result.triggered)
        self.assertFalse(result.api_key_disabled)
        self.assertTrue(result.oauth_credentials_disabled)
        identity_client.disable_api_key.assert_not_called()
        identity_client.disable_access_key.assert_called_once_with("hrn:app/target-app", "hrn:accesskey/1")

    def test_reports_disable_failure_without_raising(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="fuel-prices",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_apps.return_value = [{"id": "target-app", "hrn": "hrn:app/target-app"}]
        identity_client.list_api_keys.return_value = [{"apiKey": "hrn:apikey/1", "apiKeyId": "api-key-1", "enabled": True}]
        identity_client.list_access_keys.return_value = [{"accessKeyHrn": "hrn:accesskey/1", "accessKeyId": "client-id-1", "enabled": True}]
        identity_client.disable_api_key.side_effect = HereClientError("HTTP 403")

        with unittest.mock.patch.dict(
            os.environ,
            {
                "HERE_AUTO_DISABLE_APP_CREDENTIALS": "true",
                "HERE_MONITOR_ACCESS_KEY_ID": "monitor-client-id",
            },
            clear=False,
        ):
            result = maybe_disable_app_credentials([record], [quota], identity_client)

        self.assertTrue(result.triggered)
        self.assertFalse(result.api_key_disabled)
        self.assertTrue(result.oauth_credentials_disabled)
        self.assertIn("API key disable failed", result.message)

    def test_skips_disable_when_monitor_uses_same_app_credentials(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="fuel-prices",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_apps.return_value = [{"id": "target-app", "hrn": "hrn:app/target-app"}]
        identity_client.list_access_keys.return_value = [{"accessKeyHrn": "hrn:accesskey/1", "accessKeyId": "client-id-1", "enabled": True}]

        with unittest.mock.patch.dict(
            os.environ,
            {
                "HERE_AUTO_DISABLE_APP_CREDENTIALS": "true",
                "HERE_MONITOR_ACCESS_KEY_ID": "client-id-1",
            },
            clear=False,
        ):
            result = maybe_disable_app_credentials([record], [quota], identity_client)

        self.assertFalse(result.triggered)
        self.assertTrue(result.skipped_to_protect_monitor)
        self.assertIn("Separate the monitor credential", result.message)
        identity_client.disable_api_key.assert_not_called()
        identity_client.disable_access_key.assert_not_called()

    def test_disables_only_apps_implicated_in_exceeded_metrics(self) -> None:
        records = [
            UsageRecord(
                usage_date=date(2026, 8, 26),
                metric="Fuel Prices",
                quantity=2,
                unit="Transactions",
                feature_id="fuel-prices",
                app_id="target-app",
                project_id=None,
                billing_tag=None,
                dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
                source_retrieved_at=datetime.now(timezone.utc),
            ),
            UsageRecord(
                usage_date=date(2026, 8, 26),
                metric="Fuel Prices",
                quantity=0,
                unit="Transactions",
                feature_id="fuel-prices",
                app_id="zero-app",
                project_id=None,
                billing_tag=None,
                dimension_key='{"app_id":"zero-app","feature_id":"fuel-prices"}',
                source_retrieved_at=datetime.now(timezone.utc),
            ),
            UsageRecord(
                usage_date=date(2026, 8, 26),
                metric="Autocomplete",
                quantity=10,
                unit="Transactions",
                feature_id="autocomplete",
                app_id="other-app",
                project_id=None,
                billing_tag=None,
                dimension_key='{"app_id":"other-app","feature_id":"autocomplete"}',
                source_retrieved_at=datetime.now(timezone.utc),
            ),
        ]
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_apps.return_value = [{"id": "target-app", "hrn": "hrn:app/target-app"}]
        identity_client.list_api_keys.return_value = [{"apiKey": "hrn:apikey/1", "enabled": True}]
        identity_client.list_access_keys.return_value = [{"accessKeyHrn": "hrn:accesskey/1", "enabled": True}]

        with unittest.mock.patch.dict(os.environ, {"HERE_AUTO_DISABLE_APP_CREDENTIALS": "true"}, clear=False):
            result = maybe_disable_app_credentials(records, [quota], identity_client)

        self.assertTrue(result.triggered)
        identity_client.disable_api_key.assert_called_once_with("hrn:app/target-app", "hrn:apikey/1")
        identity_client.disable_access_key.assert_called_once_with("hrn:app/target-app", "hrn:accesskey/1")

    def test_aggregates_mixed_multi_app_disable_and_skip_outcomes(self) -> None:
        records = [
            UsageRecord(
                usage_date=date(2026, 8, 26),
                metric="Fuel Prices",
                quantity=2,
                unit="Transactions",
                feature_id="fuel-prices",
                app_id="protected-app",
                project_id=None,
                billing_tag=None,
                dimension_key='{"app_id":"protected-app","feature_id":"fuel-prices"}',
                source_retrieved_at=datetime.now(timezone.utc),
            ),
            UsageRecord(
                usage_date=date(2026, 8, 26),
                metric="Fuel Prices",
                quantity=3,
                unit="Transactions",
                feature_id="fuel-prices",
                app_id="target-app",
                project_id=None,
                billing_tag=None,
                dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
                source_retrieved_at=datetime.now(timezone.utc),
            ),
        ]
        quota = QuotaStatus("Fuel Prices", 5, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_apps.return_value = [
            {"id": "protected-app", "hrn": "hrn:app/protected-app"},
            {"id": "target-app", "hrn": "hrn:app/target-app"},
        ]

        def list_access_keys(app_hrn: str) -> list[dict[str, object]]:
            if app_hrn == "hrn:app/protected-app":
                return [{"accessKeyHrn": "hrn:accesskey/monitor", "accessKeyId": "monitor-client-id", "enabled": True}]
            if app_hrn == "hrn:app/target-app":
                return [{"accessKeyHrn": "hrn:accesskey/target", "accessKeyId": "target-client-id", "enabled": True}]
            raise AssertionError(app_hrn)

        def list_api_keys(app_hrn: str) -> list[dict[str, object]]:
            if app_hrn == "hrn:app/target-app":
                return [{"apiKey": "hrn:apikey/target", "enabled": True}]
            if app_hrn == "hrn:app/protected-app":
                return [{"apiKey": "hrn:apikey/protected", "enabled": True}]
            raise AssertionError(app_hrn)

        identity_client.list_access_keys.side_effect = list_access_keys
        identity_client.list_api_keys.side_effect = list_api_keys

        with unittest.mock.patch.dict(
            os.environ,
            {
                "HERE_AUTO_DISABLE_APP_CREDENTIALS": "true",
                "HERE_MONITOR_ACCESS_KEY_ID": "monitor-client-id",
            },
            clear=False,
        ):
            result = maybe_disable_app_credentials(records, [quota], identity_client)

        self.assertTrue(result.triggered)
        self.assertTrue(result.api_key_disabled)
        self.assertTrue(result.oauth_credentials_disabled)
        self.assertTrue(result.skipped_to_protect_monitor)
        self.assertIn("Automatic credential disable was skipped for app protected-app", result.message)
        self.assertIn("Credential auto-disable triggered for app target-app", result.message)
        identity_client.disable_api_key.assert_called_once_with("hrn:app/target-app", "hrn:apikey/target")
        identity_client.disable_access_key.assert_called_once_with("hrn:app/target-app", "hrn:accesskey/target")

    def test_project_limit_selects_allowed_service_resources_and_links_app(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="hrn:here:service::olp-here:fuel-prices-3:fleet",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_external_service_resources.return_value = [
            "hrn:here:service::olp-here:fuel-prices-3",
            "hrn:here:service::olp-here:search-autosuggest-7",
            "hrn:here:service::olp-here:routing-8",
        ]
        identity_client.list_apps.return_value = [
            {"id": "target-app", "hrn": "hrn:app/target-app", "name": "HERE TEST"}
        ]
        identity_client.list_access_keys.return_value = [
            {"accessKeyHrn": "hrn:accesskey/target", "accessKeyId": "target-key", "enabled": True}
        ]
        identity_client.create_project.return_value = {
            "id": "ua-123",
            "hrn": "hrn:project/ua-123",
            "name": "HERE TEST",
        }
        identity_client.list_projects.return_value = []
        identity_client.list_project_resources.return_value = []
        identity_client.list_project_members.return_value = []
        identity_client.add_project_resources.return_value = []

        with unittest.mock.patch.dict(
            os.environ,
            {
                "HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT": "true",
                "HERE_MONITOR_ACCESS_KEY_ID": "monitor-key",
            },
            clear=False,
        ):
            result = maybe_limit_app_to_within_free_tier_project([record], [quota], identity_client)

        self.assertTrue(result.triggered)
        identity_client.update_project_settings.assert_called_once_with("hrn:project/ua-123", "thisProjectOnly")
        identity_client.add_project_resources.assert_called_once_with(
            "hrn:project/ua-123",
            [
                "hrn:here:service::olp-here:routing-8",
                "hrn:here:service::olp-here:search-autosuggest-7",
            ],
        )
        identity_client.add_project_member.assert_called_once_with("hrn:project/ua-123", "hrn:app/target-app")
        identity_client.set_default_scope.assert_called_once_with("hrn:app/target-app", "hrn:project/ua-123")
        identity_client.delete_project.assert_not_called()

    def test_project_limit_rolls_back_created_project_when_service_linking_fails(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="hrn:here:service::olp-here:fuel-prices-3:fleet",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_external_service_resources.return_value = [
            "hrn:here:service::olp-here:fuel-prices-3",
            "hrn:here:service::olp-here:search-autosuggest-7",
        ]
        identity_client.list_apps.return_value = [
            {"id": "target-app", "hrn": "hrn:app/target-app", "name": "HERE TEST"}
        ]
        identity_client.list_access_keys.return_value = [
            {"accessKeyHrn": "hrn:accesskey/target", "accessKeyId": "target-key", "enabled": True}
        ]
        identity_client.create_project.return_value = {
            "id": "ua-123",
            "hrn": "hrn:project/ua-123",
            "name": "HERE TEST",
        }
        identity_client.list_projects.return_value = []
        identity_client.list_project_resources.return_value = []
        identity_client.list_project_members.return_value = []
        identity_client.add_project_resources.return_value = []
        identity_client.add_project_resources.side_effect = HereClientError(
            "HERE request failed with HTTP 400; code=400974; cause=Unsupported Resource Relation."
        )

        with unittest.mock.patch.dict(
            os.environ,
            {
                "HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT": "true",
                "HERE_MONITOR_ACCESS_KEY_ID": "monitor-key",
            },
            clear=False,
        ):
            result = maybe_limit_app_to_within_free_tier_project([record], [quota], identity_client)

        self.assertFalse(result.triggered)
        self.assertIn("No complete project restriction was confirmed", result.message)
        identity_client.update_project_settings.assert_called_once_with("hrn:project/ua-123", "thisProjectOnly")
        identity_client.delete_project.assert_called_once_with("hrn:project/ua-123")
        identity_client.add_project_member.assert_not_called()
        identity_client.set_default_scope.assert_not_called()
        identity_client.disable_api_key.assert_not_called()
        identity_client.disable_access_key.assert_not_called()

    def test_project_limit_takes_precedence_over_disable(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="hrn:here:service::olp-here:fuel-prices-3:fleet",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_external_service_resources.return_value = [
            "hrn:here:service::olp-here:fuel-prices-3",
            "hrn:here:service::olp-here:search-autosuggest-7",
        ]
        identity_client.list_apps.return_value = [
            {"id": "target-app", "hrn": "hrn:app/target-app", "name": "HERE TEST"}
        ]
        identity_client.list_access_keys.return_value = [
            {"accessKeyHrn": "hrn:accesskey/target", "accessKeyId": "target-key", "enabled": True}
        ]
        identity_client.create_project.return_value = {
            "id": "ua-123",
            "hrn": "hrn:project/ua-123",
            "name": "HERE TEST",
        }
        identity_client.list_projects.return_value = []
        identity_client.list_project_resources.return_value = []
        identity_client.list_project_members.return_value = []
        identity_client.add_project_resources.return_value = []
        identity_client.add_project_resources.side_effect = HereClientError("Unsupported Resource Relation")

        with unittest.mock.patch.dict(
            os.environ,
            {
                "HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT": "true",
                "HERE_AUTO_DISABLE_APP_CREDENTIALS": "true",
                "HERE_MONITOR_ACCESS_KEY_ID": "monitor-key",
            },
            clear=False,
        ):
            maybe_remediate_app_access([record], [quota], identity_client)

        identity_client.disable_api_key.assert_not_called()
        identity_client.disable_access_key.assert_not_called()

    def test_project_limit_reuses_project_and_removes_stale_exceeded_resource(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="hrn:here:service::olp-here:fuel-prices-3:fleet",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        fuel = "hrn:here:service::olp-here:fuel-prices-3"
        autosuggest = "hrn:here:service::olp-here:search-autosuggest-7"
        routing = "hrn:here:service::olp-here:routing-8"
        identity_client.list_external_service_resources.return_value = [fuel, autosuggest, routing]
        identity_client.list_projects.return_value = [
            {"id": _managed_project_id("target-app"), "hrn": "hrn:project/managed", "name": "HERE TEST"}
        ]
        identity_client.list_apps.return_value = [
            {"id": "target-app", "hrn": "hrn:app/target-app", "name": "HERE TEST"}
        ]
        identity_client.list_project_resources.return_value = [
            {"resource": fuel, "type": "service", "relation": "reference"},
            {"resource": autosuggest, "type": "service", "relation": "reference"},
        ]
        identity_client.list_project_members.return_value = []
        identity_client.add_project_resources.return_value = []

        with unittest.mock.patch.dict(
            os.environ,
            {"HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT": "true"},
            clear=False,
        ):
            result = maybe_limit_app_to_within_free_tier_project([record], [quota], identity_client)

        self.assertTrue(result.triggered)
        identity_client.create_project.assert_not_called()
        identity_client.remove_project_resource.assert_called_once_with("hrn:project/managed", fuel)
        identity_client.add_project_resources.assert_called_once_with("hrn:project/managed", [routing])
        identity_client.add_project_member.assert_called_once_with("hrn:project/managed", "hrn:app/target-app")
        identity_client.set_default_scope.assert_called_once_with("hrn:app/target-app", "hrn:project/managed")

    def test_project_limit_reports_unmapped_exceeded_service_without_allowing_everything(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 8, 26),
            metric="Fuel Prices",
            quantity=2,
            unit="Transactions",
            feature_id="fuel-prices",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"fuel-prices"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        quota = QuotaStatus("Fuel Prices", 2, 0, None, "EXCEEDED")
        identity_client = Mock()
        identity_client.list_external_service_resources.return_value = [
            "hrn:here:service::olp-here:fuel-prices-3",
            "hrn:here:service::olp-here:routing-8",
        ]
        identity_client.list_projects.return_value = []
        identity_client.list_apps.return_value = [
            {"id": "target-app", "hrn": "hrn:app/target-app", "name": "HERE TEST"}
        ]

        with unittest.mock.patch.dict(
            os.environ,
            {"HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT": "true"},
            clear=False,
        ):
            result = maybe_limit_app_to_within_free_tier_project([record], [quota], identity_client)

        self.assertFalse(result.triggered)
        self.assertIn("could not be mapped to service resources", result.message)
        identity_client.create_project.assert_not_called()
        identity_client.add_project_resources.assert_not_called()

    def test_project_limit_restores_all_services_for_existing_project_without_current_overage(self) -> None:
        record = UsageRecord(
            usage_date=date(2026, 9, 1),
            metric="Autocomplete",
            quantity=2,
            unit="Transactions",
            feature_id="hrn:here:service::olp-here:search-autocomplete-7",
            app_id="target-app",
            project_id=None,
            billing_tag=None,
            dimension_key='{"app_id":"target-app","feature_id":"autocomplete"}',
            source_retrieved_at=datetime.now(timezone.utc),
        )
        identity_client = Mock()
        fuel = "hrn:here:service::olp-here:fuel-prices-3"
        autocomplete = "hrn:here:service::olp-here:search-autocomplete-7"
        routing = "hrn:here:service::olp-here:routing-8"
        identity_client.list_external_service_resources.return_value = [fuel, autocomplete, routing]
        identity_client.list_projects.return_value = [
            {"id": _managed_project_id("target-app"), "hrn": "hrn:project/managed", "name": "HERE TEST"}
        ]
        identity_client.list_apps.return_value = [
            {"id": "target-app", "hrn": "hrn:app/target-app", "name": "HERE TEST"}
        ]
        identity_client.list_project_resources.return_value = [
            {"resource": autocomplete, "type": "service", "relation": "reference"}
        ]
        identity_client.list_project_members.return_value = [{"member": "hrn:app/target-app"}]
        identity_client.add_project_resources.return_value = []

        with unittest.mock.patch.dict(
            os.environ,
            {"HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT": "true"},
            clear=False,
        ):
            result = maybe_limit_app_to_within_free_tier_project([record], [], identity_client)

        self.assertTrue(result.triggered)
        self.assertIn("restored", result.message)
        identity_client.add_project_resources.assert_called_once_with(
            "hrn:project/managed", [fuel, routing]
        )
        identity_client.add_project_member.assert_not_called()
        identity_client.set_default_scope.assert_called_once_with("hrn:app/target-app", "hrn:project/managed")

    def test_project_limit_restores_managed_project_at_month_start_without_new_usage(self) -> None:
        identity_client = Mock()
        fuel = "hrn:here:service::olp-here:fuel-prices-3"
        routing = "hrn:here:service::olp-here:routing-8"
        identity_client.list_external_service_resources.return_value = [fuel, routing]
        identity_client.list_projects.return_value = [
            {
                "id": _managed_project_id("target-app"),
                "hrn": "hrn:project/managed",
                "name": "HERE TEST",
                "description": "Managed by usage-alert to restrict app target-app; Fuel Prices excluded.",
            }
        ]
        identity_client.list_apps.return_value = [
            {"id": "target-app", "hrn": "hrn:app/target-app", "name": "HERE TEST"}
        ]
        identity_client.list_project_resources.return_value = [
            {"resource": routing, "type": "service", "relation": "reference"}
        ]
        identity_client.list_project_members.return_value = [{"member": "hrn:app/target-app"}]
        identity_client.add_project_resources.return_value = []

        with unittest.mock.patch.dict(
            os.environ,
            {"HERE_LIMIT_APP_TO_WITHIN_FREE_TIER_PROJECT": "true"},
            clear=False,
        ):
            result = maybe_limit_app_to_within_free_tier_project([], [], identity_client)

        self.assertTrue(result.triggered)
        self.assertIn("restored", result.message)
        identity_client.add_project_resources.assert_called_once_with("hrn:project/managed", [fuel])
        identity_client.set_default_scope.assert_called_once_with("hrn:app/target-app", "hrn:project/managed")
