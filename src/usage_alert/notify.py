from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import Anomaly


class NotificationError(RuntimeError):
    """Raised when an alert webhook cannot accept a notification."""


def build_webhook_payload(anomalies: list[Anomaly], report_path: str) -> dict[str, object]:
    return {
        "event": "here_usage_anomaly",
        "severity": "critical" if any(item.severity == "critical" for item in anomalies) else "warning",
        "usage_date_utc": anomalies[0].record.usage_date.isoformat(),
        "anomaly_count": len(anomalies),
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
        "note": "Root-cause hypotheses require corroboration from deployment and application telemetry.",
    }


def notify_webhook(anomalies: list[Anomaly], report_path: str) -> bool:
    """POST one alert per run when a webhook URL is configured."""
    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not anomalies or not webhook_url:
        return False
    body = json.dumps(build_webhook_payload(anomalies, report_path)).encode("utf-8")
    request = Request(webhook_url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            if not 200 <= response.status < 300:
                raise NotificationError(f"Alert webhook returned HTTP {response.status}.")
    except (HTTPError, URLError) as error:
        raise NotificationError("Alert webhook request failed.") from error
    return True