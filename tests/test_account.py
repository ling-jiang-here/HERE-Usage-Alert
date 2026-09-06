from __future__ import annotations

import unittest

from usage_alert.account import (
    ACCOUNT_TYPE_DEVELOPER,
    ACCOUNT_TYPE_NAMED_OR_PARTNER,
    AccountProbe,
    ProductProbe,
    probe_account,
)
from usage_alert.client import HereUsageClient


def _active_subscription(subscription_id: str = "SUBSCRIPTION-1") -> dict[str, object]:
    return {"id": subscription_id, "status": "active", "contractStartDate": "2025-11-17", "contractEndDate": "2026-11-17"}


def _terminated_subscription(subscription_id: str = "SUBSCRIPTION-2") -> dict[str, object]:
    return {"id": subscription_id, "status": "terminated"}


def _product(name: str, plan_hrn: str | None = None) -> dict[str, object]:
    product: dict[str, object] = {"id": "PRODUCT-1", "name": name, "accessPlanIdList": []}
    if plan_hrn:
        product["accessPlanIdList"] = [{"planHrn": plan_hrn, "type": "plan", "id": "PLAN-1"}]  # type: ignore[assignment]
    return product


class FakeClient:
    def __init__(self) -> None:
        self.subscriptions: list[dict[str, object]] = []
        self.products_by_subscription: dict[str, list[dict[str, object]]] = {}
        self.app_plans: list[object] = []

    def fetch_bam_subscriptions(self) -> list[dict[str, object]]:
        return self.subscriptions

    def fetch_bam_subscription_products(self, subscription_id: str) -> list[dict[str, object]]:
        return self.products_by_subscription.get(subscription_id, [])

    def fetch_app_authorization(self) -> dict[str, object]:
        return {"app": {"clientId": "monitor-app"}, "plans": list(self.app_plans), "policies": []}


class ProbeAccountTests(unittest.TestCase):
    def test_no_subscriptions_is_a_developer_account(self) -> None:
        client = FakeClient()
        client.subscriptions = []

        probe = probe_account(client)

        self.assertEqual(ACCOUNT_TYPE_DEVELOPER, probe.account_type)
        self.assertTrue(probe.is_developer)
        self.assertEqual(0, probe.active_subscription_count)

    def test_only_free_developer_products_is_a_developer_account(self) -> None:
        client = FakeClient()
        client.subscriptions = [
            _active_subscription("SUBSCRIPTION-A"),
            _terminated_subscription("SUBSCRIPTION-B"),
        ]
        client.products_by_subscription["SUBSCRIPTION-A"] = [
            _product("HERE SDK Explore Edition v2.0"),
            _product("HERE SDK EXPLORE for Flutter"),
        ]

        probe = probe_account(client)

        self.assertEqual(ACCOUNT_TYPE_DEVELOPER, probe.account_type)
        self.assertEqual(1, probe.active_subscription_count)
        self.assertEqual(1, probe.terminated_subscription_count)
        self.assertEqual(2, len(probe.products))
        self.assertTrue(all(product.is_developer for product in probe.products))

    def test_active_subscription_with_non_developer_product_is_named_or_partner(self) -> None:
        client = FakeClient()
        client.subscriptions = [_active_subscription("SUBSCRIPTION-A")]
        client.products_by_subscription["SUBSCRIPTION-A"] = [
            _product("HERE SDK Explore Edition v2.0", "hrn:here:authorization::HERE:plan/PLAN-free"),
            _product("HERE Routing API Enhanced", "hrn:here:authorization::HERE:plan/PLAN-paid"),
        ]

        probe = probe_account(client)

        self.assertEqual(ACCOUNT_TYPE_NAMED_OR_PARTNER, probe.account_type)
        self.assertTrue(probe.is_named_or_partner)
        self.assertIn("HERE Routing API Enhanced", probe.reason)
        self.assertEqual([True, False], [product.is_developer for product in probe.products])

    def test_developer_products_but_linked_iam_plans_is_named_or_partner(self) -> None:
        client = FakeClient()
        client.subscriptions = [_active_subscription("SUBSCRIPTION-A")]
        client.products_by_subscription["SUBSCRIPTION-A"] = [_product("HERE SDK Explore Edition v2.0")]
        client.app_plans = [{"planHrn": "hrn:here:authorization::HERE:plan/PLAN-linked"}]

        probe = probe_account(client)

        self.assertEqual(ACCOUNT_TYPE_NAMED_OR_PARTNER, probe.account_type)
        self.assertEqual(1, probe.monitor_app_plan_count)

    def test_only_terminated_subscriptions_is_a_developer_account(self) -> None:
        client = FakeClient()
        client.subscriptions = [_terminated_subscription("SUBSCRIPTION-B")]

        probe = probe_account(client)

        self.assertEqual(ACCOUNT_TYPE_DEVELOPER, probe.account_type)
        self.assertEqual(0, probe.active_subscription_count)
        self.assertEqual(1, probe.terminated_subscription_count)

    def test_custom_developer_markers_override_the_defaults(self) -> None:
        client = FakeClient()
        client.subscriptions = [_active_subscription("SUBSCRIPTION-A")]
        client.products_by_subscription["SUBSCRIPTION-A"] = [_product("HERE SDK Explore Edition v2.0")]

        probe = probe_account(client, developer_product_markers=("premium",))

        self.assertEqual(ACCOUNT_TYPE_NAMED_OR_PARTNER, probe.account_type)
        self.assertFalse(probe.products[0].is_developer)

    def test_probe_is_a_frozen_dataclass(self) -> None:
        probe = AccountProbe(account_type=ACCOUNT_TYPE_DEVELOPER, reason="reason")
        product = ProductProbe(subscription_id="SUBSCRIPTION-A", name="HERE SDK Explore Edition v2.0")
        self.assertIsInstance(probe, AccountProbe)
        self.assertIsInstance(product, ProductProbe)
        self.assertTrue(product.name)


if __name__ == "__main__":
    unittest.main()