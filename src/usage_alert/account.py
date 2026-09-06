from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .client import HereUsageClient

ACCOUNT_TYPE_DEVELOPER = "developer"
ACCOUNT_TYPE_NAMED_OR_PARTNER = "named_or_partner"
ACCOUNT_TYPE_UNKNOWN = "unknown"

DEFAULT_DEVELOPER_PRODUCT_MARKERS = (
    "explore",
    "freemium",
    "trial",
    "sandbox",
    "developer",
    "base plan",
)


@dataclass(frozen=True)
class ProductProbe:
    subscription_id: str
    name: str
    plan_hrns: tuple[str, ...] = ()
    is_developer: bool = False


@dataclass(frozen=True)
class AccountProbe:
    account_type: str
    reason: str
    active_subscription_count: int = 0
    terminated_subscription_count: int = 0
    products: tuple[ProductProbe, ...] = ()
    monitor_app_plan_count: int = 0
    developer_product_markers: tuple[str, ...] = ()

    @property
    def is_developer(self) -> bool:
        return self.account_type == ACCOUNT_TYPE_DEVELOPER

    @property
    def is_named_or_partner(self) -> bool:
        return self.account_type == ACCOUNT_TYPE_NAMED_OR_PARTNER


def probe_account(
    client: HereUsageClient,
    developer_product_markers: Iterable[str] = DEFAULT_DEVELOPER_PRODUCT_MARKERS,
) -> AccountProbe:
    """Classify the realm as developer or named/partner using BAM commercial subscriptions.

    Developer (Base Plan) realms may still show BAM subscriptions for free products
    (for example the HERE SDK Explore Edition); the classification therefore marks a
    subscription product as a developer product when its name matches one of the
    configured markers, and only schedules account types as named/partner when an
    active subscription carries a non-developer product or the monitor app is linked
    to an IAM plan.
    """
    markers = tuple(marker.strip().lower() for marker in developer_product_markers if marker and marker.strip())

    def account_probe(account_type: str, reason: str, **fields: object) -> AccountProbe:
        return AccountProbe(
            account_type=account_type,
            reason=reason,
            developer_product_markers=markers,
            **fields,
        )

    subscriptions = client.fetch_bam_subscriptions()
    active = [subscription for subscription in subscriptions if subscription.get("status") == "active"]
    terminated = len(subscriptions) - len(active)
    if not subscriptions:
        return account_probe(
            ACCOUNT_TYPE_DEVELOPER,
            "No BAM subscriptions exist for the realm; this matches a developer/Base Plan account.",
        )

    products: list[ProductProbe] = []
    for subscription in active:
        subscription_id = subscription.get("id")
        if not isinstance(subscription_id, str):
            continue
        for product in client.fetch_bam_subscription_products(subscription_id):
            name = str(product.get("name") or "")
            plan_hrns = tuple(
                access.get("planHrn")
                for access in (product.get("accessPlanIdList") or [])
                if isinstance(access, dict) and access.get("planHrn")
            )
            products.append(ProductProbe(subscription_id, name, plan_hrns, _is_developer_product(name, markers)))

    commercial = [product for product in products if not product.is_developer]
    if commercial:
        names = ", ".join(sorted({product.name for product in commercial}))
        return account_probe(
            ACCOUNT_TYPE_NAMED_OR_PARTNER,
            f"Active BAM subscription carries non-developer product: {names}.",
            active_subscription_count=len(active),
            terminated_subscription_count=terminated,
            products=tuple(products),
        )

    app_plans = (client.fetch_app_authorization().get("plans") or [])
    if isinstance(app_plans, list) and app_plans:
        return account_probe(
            ACCOUNT_TYPE_NAMED_OR_PARTNER,
            "No active commercial product, but the monitor app is linked to IAM plans.",
            active_subscription_count=len(active),
            terminated_subscription_count=terminated,
            products=tuple(products),
            monitor_app_plan_count=len(app_plans),
        )

    if not active:
        return account_probe(
            ACCOUNT_TYPE_DEVELOPER,
            "No active BAM subscription exists for the realm.",
            active_subscription_count=0,
            terminated_subscription_count=terminated,
            products=tuple(products),
        )

    return account_probe(
        ACCOUNT_TYPE_DEVELOPER,
        "All active subscription products are developer/free-tier products.",
        active_subscription_count=len(active),
        terminated_subscription_count=terminated,
        products=tuple(products),
    )


def _is_developer_product(name: str, markers: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return bool(markers) and any(marker in lowered for marker in markers)