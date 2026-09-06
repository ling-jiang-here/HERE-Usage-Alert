from __future__ import annotations

import json
import math
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import Anomaly, UsageRecord
from .quota import QuotaStatus
from .report import summarize_usage
from .rules import RuleAlert


class NotificationError(RuntimeError):
    """Raised when an alert webhook cannot accept a notification."""


def build_webhook_payload(
    anomalies: list[Anomaly], report_path: str, quota_alerts: list[QuotaStatus] | None = None,
    remediation_note: str | None = None, rule_alerts: list[RuleAlert] | None = None,
) -> dict[str, object]:
    quota_alerts = quota_alerts or []
    rule_alerts = rule_alerts or []
    note = "Root-cause hypotheses require corroboration from deployment and application telemetry."
    if remediation_note:
        note = f"{note} {remediation_note}"
    return {
        "event": "here_usage_alert",
        "severity": "critical" if any(item.severity == "critical" for item in anomalies) else "warning",
        "usage_date_utc": anomalies[0].record.usage_date.isoformat(),
        "anomaly_count": len(anomalies),
        "quota_alert_count": len(quota_alerts),
        "rule_alert_count": len(rule_alerts),
        "report_path": report_path,
        "anomalies": [
            {
                "severity": item.severity,
                "metric": item.record.metric,
                "feature_id": item.record.feature_id,
                "app_id": item.record.app_id,
                "observed_quantity": item.record.quantity,
                "baseline_median": item.baseline_median,
                "absolute_increase": item.absolute_increase,
                "percentage_increase": item.percentage_increase,
                "baseline_sample_size": item.baseline_sample_size,
                "robust_z_score": item.robust_z_score,
            }
            for item in anomalies
        ],
        "quota_alerts": [
            {
                "metric": item.metric,
                "usage": item.usage,
                "allowance": item.allowance,
                "percentage": _finite_or_none(item.percentage),
                "status": item.status,
                "unit": item.unit,
            }
            for item in quota_alerts
        ],
        "rule_alerts": [_rule_alert_json(item) for item in rule_alerts],
        "note": note,
    }


def build_quota_alert_payload(
    records: list[UsageRecord], quota_alerts: list[QuotaStatus], report_path: str,
    remediation_note: str | None = None, rule_alerts: list[RuleAlert] | None = None,
) -> dict[str, object]:
    quota_alerts = quota_alerts or []
    rule_alerts = rule_alerts or []
    note = "Configured free-tier usage limits were exceeded."
    if remediation_note:
        note = f"{note} {remediation_note}"
    return {
        "event": "here_usage_alert",
        "severity": "warning",
        "usage_date_utc": records[0].usage_date.isoformat(),
        "anomaly_count": 0,
        "quota_alert_count": len(quota_alerts),
        "rule_alert_count": len(rule_alerts),
        "report_path": report_path,
        "anomalies": [],
        "quota_alerts": [
            {
                "metric": item.metric,
                "usage": item.usage,
                "allowance": item.allowance,
                "percentage": _finite_or_none(item.percentage),
                "status": item.status,
                "unit": item.unit,
            }
            for item in quota_alerts
        ],
        "rule_alerts": [_rule_alert_json(item) for item in rule_alerts],
        "note": note,
    }


def build_rule_alert_payload(
    records: list[UsageRecord], rule_alerts: list[RuleAlert], report_path: str,
    usage_date_utc: str | None = None, remediation_note: str | None = None,
) -> dict[str, object]:
    if usage_date_utc is None:
        if not records:
            raise ValueError("A usage date is required when sending rule alerts without records")
        usage_date_utc = records[0].usage_date.isoformat()
    note = f"{len(rule_alerts)} configured Usage Alert threshold(s) were crossed."
    if remediation_note:
        note = f"{note} {remediation_note}"
    severity = "critical" if any(alert.observed >= alert.threshold * 2 for alert in rule_alerts) else "warning"
    return {
        "event": "here_rule_alert",
        "severity": severity,
        "usage_date_utc": usage_date_utc,
        "anomaly_count": 0,
        "quota_alert_count": 0,
        "rule_alert_count": len(rule_alerts),
        "report_path": report_path,
        "anomalies": [],
        "quota_alerts": [],
        "rule_alerts": [_rule_alert_json(item) for item in rule_alerts],
        "note": note,
    }


def build_healthy_webhook_payload(
    records: list[UsageRecord], report_path: str, usage_date_utc: str | None = None,
    remediation_note: str | None = None, rule_alerts: list[RuleAlert] | None = None,
) -> dict[str, object]:
    if usage_date_utc is None:
        if not records:
            raise ValueError("A usage date is required when sending a healthy webhook without records")
        usage_date_utc = records[0].usage_date.isoformat()
    note = "Usage monitoring completed successfully. No anomaly met the configured threshold."
    if remediation_note:
        note = f"{note} {remediation_note}"
    rule_alerts = rule_alerts or []
    return {
        "event": "here_usage_healthy",
        "severity": "info",
        "usage_date_utc": usage_date_utc,
        "usage_series_count": len(records),
        "usage_summary": [
            {"unit": unit, "metric": metric, "quantity": quantity}
            for unit, metric, quantity in summarize_usage(records)
        ],
        "anomaly_count": 0,
        "quota_alert_count": 0,
        "rule_alert_count": len(rule_alerts),
        "rule_alerts": [_rule_alert_json(item) for item in rule_alerts],
        "report_path": report_path,
        "note": note,
    }


def notify_webhook(
    anomalies: list[Anomaly], records: list[UsageRecord], report_path: str,
    quota_alerts: list[QuotaStatus] | None = None,
    remediation_note: str | None = None,
    usage_date_utc: str | None = None,
    rule_alerts: list[RuleAlert] | None = None,
) -> bool:
    """POST a success or alert event after each completed monitoring run.

    Notifications always use the project ALERT_WEBHOOK_URL; webhooks or email lists
    configured on the imported usage alert rules are never contacted.
    """
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False
    quota_alerts = quota_alerts or []
    rule_alerts = rule_alerts or []
    if anomalies:
        payload = build_webhook_payload(anomalies, report_path, quota_alerts, remediation_note, rule_alerts)
    elif quota_alerts:
        payload = build_quota_alert_payload(records, quota_alerts, report_path, remediation_note, rule_alerts)
    elif rule_alerts:
        payload = build_rule_alert_payload(records, rule_alerts, report_path, usage_date_utc, remediation_note)
    else:
        payload = build_healthy_webhook_payload(records, report_path, usage_date_utc, remediation_note, rule_alerts)
    body = json.dumps(payload, allow_nan=False).encode("utf-8")
    request = Request(
        webhook_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "HERE-Usage-Alert/0.1"},
    )
    try:
        with urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise NotificationError(f"Alert webhook returned HTTP {response.status}.")
    except (HTTPError, URLError) as error:
        raise NotificationError("Alert webhook request failed.") from error
    return True


def _finite_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return value if math.isfinite(value) else None


def _rule_alert_json(alert: RuleAlert) -> dict[str, object]:
    return {
        "rule_id": alert.rule.id,
        "rule_name": alert.rule.name,
        "threshold": alert.threshold,
        "observed": alert.observed,
        "exceeded_by": alert.exceeded_by,
        "unit": alert.unit,
        "app_id": alert.app_id,
        "feature_id": alert.feature_id,
        "time_range_duration": alert.rule.time_range_duration,
    }