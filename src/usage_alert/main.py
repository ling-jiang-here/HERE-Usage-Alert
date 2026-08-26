from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .client import HereUsageClient
from .config import load_detection_config, load_dotenv
from .detect import detect_anomalies, detect_hourly_anomalies
from .notify import notify_webhook
from .normalize import normalize_records
from .quota import evaluate_month_to_date, load_free_tiers
from .report import render_daily_report, render_hourly_report, write_daily_report, write_hourly_report
from .storage import read_records, write_daily_records, write_hourly_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor HERE organization usage for daily anomalies.")
    parser.add_argument("--date", type=date.fromisoformat, help="Completed UTC usage date (YYYY-MM-DD).")
    parser.add_argument("--hourly", action="store_true", help="Check the completed UTC hour and report anomalies only.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Recorded JSON response using the temporary fixture contract.")
    source.add_argument("--fetch", action="store_true", help="Fetch a live response using the configured HERE client.")
    source.add_argument("--test-webhook", action="store_true", help="Send one synthetic webhook smoke-test event.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Project root for data and reports.")
    arguments = parser.parse_args()

    load_dotenv(arguments.root / ".env")
    target_date = arguments.date or date.today() - timedelta(days=1)
    persist_outputs = arguments.input is not None
    if arguments.test_webhook:
        test_anomaly = _synthetic_test_anomaly()
        notified = notify_webhook([test_anomaly], [test_anomaly.record], "synthetic-webhook-test")
        print(f"Webhook smoke test sent: {'yes' if notified else 'no'}")
        return 0 if notified else 1
    if arguments.hourly:
        target_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        config = load_detection_config(arguments.root / "config" / "thresholds.json")
        if arguments.fetch:
            raw_payload = HereUsageClient().fetch_hourly_history(target_hour, config.history_days)
            payload = json.loads(raw_payload)
        else:
            payload = json.loads(arguments.input.read_text(encoding="utf-8"))
        records = normalize_records(payload, preserve_hours=True)
        hourly_records = [record for record in records if record.usage_hour_utc == target_hour]
        if not hourly_records:
            raise ValueError(f"Input has no records for {target_hour.isoformat()}")
        if arguments.fetch:
            all_records = [
                record for record in records
                if record.usage_hour_utc is not None
                and record.usage_hour_utc <= target_hour
                and record.usage_hour_utc.hour == target_hour.hour
            ]
        else:
            hourly_directory = arguments.root / "data" / "hourly"
            history = [record for record in read_records(hourly_directory) if record.usage_hour_utc != target_hour]
            write_hourly_records(hourly_records, hourly_directory)
            all_records = history + hourly_records
        anomalies = detect_hourly_anomalies(all_records, target_hour, config)
        if not anomalies:
            print(f"No hourly anomaly for {target_hour.isoformat()}; no report written.")
            return 0
        report = render_hourly_report(hourly_records, anomalies)
        report_reference = f"hourly:{target_hour.isoformat()}"
        if persist_outputs:
            report_path = write_hourly_report(report, arguments.root / "reports", target_hour)
            report_reference = str(report_path)
            print(f"Wrote hourly anomaly report: {report_path}")
        notified = notify_webhook(anomalies, hourly_records, report_reference)
        print(f"Webhook event sent: {'yes' if notified else 'no'}")
        return 0
    config = load_detection_config(arguments.root / "config" / "thresholds.json")
    if arguments.fetch:
        history_start = target_date - timedelta(days=config.history_days)
        month_start = target_date.replace(day=1)
        raw_payload = HereUsageClient().fetch_usage_range(min(history_start, month_start), target_date)
        payload = json.loads(raw_payload)
    else:
        payload = json.loads(arguments.input.read_text(encoding="utf-8"))

    records = normalize_records(payload)
    daily_records = [record for record in records if record.usage_date == target_date]
    if not daily_records:
        raise ValueError(f"Input has no records for {target_date.isoformat()}")
    if arguments.fetch:
        history_start = target_date - timedelta(days=config.history_days)
        all_records = [record for record in records if history_start <= record.usage_date <= target_date]
    else:
        curated_directory = arguments.root / "data" / "curated"
        history = [record for record in read_records(curated_directory) if record.usage_date != target_date]
        write_daily_records(daily_records, curated_directory)
        all_records = history + daily_records
    anomalies = detect_anomalies(all_records, target_date, config)
    threshold, free_tiers, data_io_free_gb = load_free_tiers(arguments.root / "config" / "free_tiers.json")
    month_records = [
        record for record in all_records
        if record.usage_date.year == target_date.year and record.usage_date.month == target_date.month
    ]
    quota_statuses = evaluate_month_to_date(month_records, threshold, free_tiers, data_io_free_gb)
    quota_alerts = [quota for quota in quota_statuses if quota.status == "EXCEEDED"]
    report = render_daily_report(daily_records, anomalies, quota_statuses)
    report_reference = f"daily:{target_date.isoformat()}"
    if persist_outputs:
        report_path = write_daily_report(report, arguments.root / "reports", target_date.isoformat())
        report_reference = str(report_path)
        print(f"Wrote report: {report_path}")
    elif anomalies or quota_alerts:
        print("Daily alerts detected; report not persisted in fetch mode.")
    print(f"Anomalies: {len(anomalies)}")
    notified = notify_webhook(anomalies, daily_records, report_reference, quota_alerts) if anomalies or quota_alerts or persist_outputs else False
    print(f"Webhook event sent: {'yes' if notified else 'no'}")
    return 0


def _synthetic_test_anomaly():
    from .models import Anomaly, UsageRecord

    record = UsageRecord(
        usage_date=date.today(),
        metric="synthetic_webhook_test",
        quantity=2_000,
        unit="events",
        feature_id="synthetic",
        app_id="github-actions",
        project_id=None,
        billing_tag=None,
        dimension_key='{"app_id":"github-actions","feature_id":"synthetic"}',
        source_retrieved_at=datetime.now(timezone.utc),
    )
    return Anomaly(
        record=record,
        baseline_median=100,
        baseline_sample_size=14,
        absolute_increase=1_900,
        percentage_increase=19.0,
        robust_z_score=10.0,
        severity="critical",
    )


if __name__ == "__main__":
    raise SystemExit(main())