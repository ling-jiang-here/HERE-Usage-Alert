from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import Anomaly, UsageRecord
from .quota import QuotaStatus
from .report import summarize_usage


class NotificationError(RuntimeError):
    """Raised when an alert webhook cannot accept a notification."""


def build_webhook_payload(
    anomalies: list[Anomaly], report_path: str, quota_alerts: list[QuotaStatus] | None = None
) -> dict[str, object]:
    quota_alerts = quota_alerts or []
    return {
        "event": "here_usage_alert",
        "severity": "critical" if any(item.severity == "critical" for item in anomalies) else "warning",
        "usage_date_utc": anomalies[0].record.usage_date.isoformat(),
        "anomaly_count": len(anomalies),
        "quota_alert_count": len(quota_alerts),
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
                "percentage": item.percentage,
                "status": item.status,
                "unit": item.unit,
            }
            for item in quota_alerts
        ],
        "note": "Root-cause hypotheses require corroboration from deployment and application telemetry.",
    }


def build_quota_alert_payload(records: list[UsageRecord], quota_alerts: list[QuotaStatus], report_path: str) -> dict[str, object]:
    return {
        "event": "here_usage_alert",
        "severity": "warning",
        "usage_date_utc": records[0].usage_date.isoformat(),
        "anomaly_count": 0,
        "quota_alert_count": len(quota_alerts),
        "report_path": report_path,
        "anomalies": [],
        "quota_alerts": [
            {
                "metric": item.metric,
                "usage": item.usage,
                "allowance": item.allowance,
                "percentage": item.percentage,
                "status": item.status,
                "unit": item.unit,
            }
            for item in quota_alerts
        ],
        "note": "Configured free-tier usage limits were exceeded.",
    }


def build_healthy_webhook_payload(records: list[UsageRecord], report_path: str) -> dict[str, object]:
    return {
        "event": "here_usage_healthy",
        "severity": "info",
        "usage_date_utc": records[0].usage_date.isoformat(),
        "usage_series_count": len(records),
        "usage_summary": [
            {"unit": unit, "metric": metric, "quantity": quantity}
            for unit, metric, quantity in summarize_usage(records)
        ],
        "anomaly_count": 0,
        "report_path": report_path,
        "note": "Usage monitoring completed successfully. No anomaly met the configured threshold.",
    }


def notify_webhook(
    anomalies: list[Anomaly], records: list[UsageRecord], report_path: str,
    quota_alerts: list[QuotaStatus] | None = None,
) -> bool:
    """POST a success or anomaly event after each completed monitoring run."""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False
    quota_alerts = quota_alerts or []
    if anomalies:
        payload = build_webhook_payload(anomalies, report_path, quota_alerts)
    elif quota_alerts:
        payload = build_quota_alert_payload(records, quota_alerts, report_path)
    else:
        payload = build_healthy_webhook_payload(records, report_path)
    body = json.dumps(payload).encode("utf-8")
    request = Request(webhook_url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise NotificationError(f"Alert webhook returned HTTP {response.status}.")
    except (HTTPError, URLError) as error:
        raise NotificationError("Alert webhook request failed.") from error
    return True