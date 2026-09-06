from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from .models import UsageRecord

_FIELD_KEYS = {
    "appId": "app_id",
    "featureId": "feature_id",
    "billingTag": "billing_tag",
    "projectHrn": "project_id",
    "project_id": "project_id",
    "metric": "metric",
}


@dataclass(frozen=True)
class QueryCondition:
    key: str
    value: str

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> QueryCondition:
        return cls(_required_string(item, "key"), _required_string(item, "value"))

    def to_dict(self) -> dict[str, str]:
        return {"key": self.key, "value": self.value}


@dataclass(frozen=True)
class UsageThresholdCondition:
    threshold_type: str
    threshold: float
    actions: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> UsageThresholdCondition:
        actions = item.get("actions", [])
        if not isinstance(actions, list):
            actions = []
        return cls(
            _required_string(item, "thresholdType"),
            _required_number(item, "threshold"),
            tuple(str(action) for action in actions if isinstance(action, str)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "thresholdType": self.threshold_type,
            "threshold": self.threshold,
            "actions": list(self.actions),
        }


@dataclass(frozen=True)
class UsageAlertRule:
    id: str
    name: str
    description: str
    query_conditions: tuple[QueryCondition, ...] = ()
    threshold_conditions: tuple[UsageThresholdCondition, ...] = ()
    time_range_duration: str = "daily"
    status: str = "active"
    email_notifications: tuple[str, ...] = ()
    webhook_url: str | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def absolute_threshold(self) -> float | None:
        values = [
            condition.threshold
            for condition in self.threshold_conditions
            if condition.threshold_type == "absolute"
        ]
        return max(values) if values else None

    def matches_record(self, record: UsageRecord) -> bool:
        for condition in self.query_conditions:
            field_name = _FIELD_KEYS.get(condition.key)
            if field_name is None:
                continue
            value = getattr(record, field_name)
            if str(value or "") != condition.value:
                return False
        return True

    @classmethod
    def from_dict(cls, item: dict[str, Any]) -> UsageAlertRule:
        query_items = item.get("queryConditions")
        if not isinstance(query_items, list):
            query_items = []
        threshold_items = item.get("usageThresholdConditions")
        if not isinstance(threshold_items, list):
            threshold_items = []
        emails = item.get("emailNotifications", [])
        if not isinstance(emails, list):
            emails = []
        time_range = item.get("timeRange")
        if not isinstance(time_range, dict):
            time_range = {}
        webhook_url = item.get("webhookUrl")
        return cls(
            id=_required_string(item, "id"),
            name=_required_string(item, "name"),
            description=_as_string(item.get("description", "")),
            query_conditions=tuple(QueryCondition.from_dict(entry) for entry in query_items),
            threshold_conditions=tuple(UsageThresholdCondition.from_dict(entry) for entry in threshold_items),
            time_range_duration=_as_string(time_range.get("duration", "daily")) or "daily",
            status=_as_string(item.get("status", "active")) or "active",
            email_notifications=tuple(str(email) for email in emails),
            webhook_url=_as_string(webhook_url) or (None if webhook_url is None else ""),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "queryConditions": [condition.to_dict() for condition in self.query_conditions],
            "usageThresholdConditions": [condition.to_dict() for condition in self.threshold_conditions],
            "timeRange": {"duration": self.time_range_duration},
            "status": self.status,
            "emailNotifications": list(self.email_notifications),
            "webhookUrl": self.webhook_url,
        }


@dataclass(frozen=True)
class RuleAlert:
    rule: UsageAlertRule
    observed: float
    threshold: float
    unit: str
    app_id: str | None
    feature_id: str | None

    @property
    def exceeded_by(self) -> float:
        return self.observed - self.threshold


@dataclass(frozen=True)
class SavedUsageAlertRules:
    """Usage alert rules persisted to the repository by the monitor."""
    retrieved_at_utc: datetime | None = None
    rules: tuple[UsageAlertRule, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SavedUsageAlertRules:
        raw_rules = payload.get("rules", [])
        if not isinstance(raw_rules, list):
            raw_rules = []
        retrieved = payload.get("retrieved_at_utc")
        return cls(
            retrieved_at_utc=datetime.fromisoformat(retrieved) if isinstance(retrieved, str) else None,
            rules=tuple(UsageAlertRule.from_dict(item) for item in raw_rules),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "retrieved_at_utc": (
                self.retrieved_at_utc.isoformat() if self.retrieved_at_utc is not None else None
            ),
            "rules": [rule.to_dict() for rule in self.rules],
        }


def parse_usage_alert_rules(payload: dict[str, Any]) -> list[UsageAlertRule]:
    """Parse the HERE Usage Alert API response into validated rules."""
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Usage Alert rules response did not include an 'items' list.")
    return [UsageAlertRule.from_dict(item) for item in items]


def evaluate_usage_alert_rules(records: list[UsageRecord], rules: list[UsageAlertRule]) -> list[RuleAlert]:
    """Return a RuleAlert for every active daily rule whose matched usage meets its threshold.

    Notifications are never sent to the webhooks or emails configured on the rules; rule
    execution only derives thresholds, and alerting always uses the project webhook.
    """
    alerts: list[RuleAlert] = []
    for rule in rules:
        if not rule.is_active:
            continue
        if rule.time_range_duration != "daily":
            continue
        threshold = rule.absolute_threshold
        if threshold is None:
            continue
        matched = [record for record in records if rule.matches_record(record)]
        if not matched:
            continue
        observed = sum(record.quantity for record in matched)
        if observed < threshold:
            continue
        apex = max(matched, key=lambda record: record.quantity)
        alerts.append(RuleAlert(rule, observed, threshold, apex.unit, apex.app_id, apex.feature_id))
    return alerts


def synthetic_usage_record_for_rule(
    rule: UsageAlertRule, usage_date: date, over_by: float = 1.0
) -> UsageRecord:
    """Build a UsageRecord that deliberately exceeds the rule's absolute threshold."""
    threshold = rule.absolute_threshold
    if threshold is None:
        raise ValueError("Rule has no absolute threshold to synthesize.")
    by_key: dict[str, str] = {}
    feature_id: str | None = None
    app_id: str | None = None
    for condition in rule.query_conditions:
        if condition.key in ("featureId", "appId") and condition.value:
            by_key[condition.key] = condition.value
        if condition.key == "featureId":
            feature_id = condition.value
        elif condition.key == "appId":
            app_id = condition.value
    return UsageRecord(
        usage_date=usage_date,
        metric="transactions",
        quantity=threshold + over_by,
        unit="Transactions",
        feature_id=feature_id,
        app_id=app_id,
        project_id=next(
            (condition.value for condition in rule.query_conditions if condition.key == "projectHrn"),
            None,
        ),
        billing_tag=next(
            (condition.value for condition in rule.query_conditions if condition.key == "billingTag"),
            None,
        ),
        dimension_key=json.dumps(by_key, sort_keys=True, separators=(",", ":")),
        source_retrieved_at=datetime.now(timezone.utc),
    )


def _required_string(item: dict[str, Any], field_name: str) -> str:
    value = item.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Usage Alert rule field '{field_name}' is missing or invalid.")
    return value.strip()


def _required_number(item: dict[str, Any], field_name: str) -> float:
    value = item.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Usage Alert rule field '{field_name}' is missing or invalid.")
    return float(value)


def _as_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None