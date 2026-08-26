from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .client import HereUsageClient
from .config import load_detection_config, load_dotenv
from .detect import detect_anomalies, detect_hourly_anomalies
from .notify import notify_webhook
from .normalize import normalize_records
from .quota import evaluate_month_to_date, load_free_tiers
from .report import render_daily_report, render_hourly_report, write_daily_report, write_hourly_report
from .storage import prune_daily_files, prune_hourly_files, read_records, write_daily_records, write_hourly_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor HERE organization usage for daily anomalies.")
    parser.add_argument("--date", type=date.fromisoformat, help="Completed UTC usage date (YYYY-MM-DD).")
    parser.add_argument("--hourly", action="store_true", help="Check usage from the last 65 minutes and report anomalies only.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Recorded JSON response using the temporary fixture contract.")
    source.add_argument("--fetch", action="store_true", help="Fetch a live response using the configured HERE client.")
    source.add_argument("--test-webhook", action="store_true", help="Send one synthetic webhook smoke-test event.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Project root for data and reports.")
    arguments = parser.parse_args()

    load_dotenv(arguments.root / ".env")
    target_date = arguments.date or date.today() - timedelta(days=1)
    if arguments.test_webhook:
        test_anomaly = _synthetic_test_anomaly()
        notified = notify_webhook([test_anomaly], [test_anomaly.record], "synthetic-webhook-test")
        print(f"Webhook smoke test sent: {'yes' if notified else 'no'}")
        return 0 if notified else 1
    if arguments.hourly:
        window_end = datetime.now(timezone.utc).replace(microsecond=0)
        window_start = window_end - timedelta(minutes=65)
        target_hour = window_end.replace(minute=0, second=0, microsecond=0)
        config = load_detection_config(arguments.root / "config" / "thresholds.json")
        if arguments.fetch:
            raw_payload = HereUsageClient().fetch_usage_window(window_start, window_end)
            payload = json.loads(raw_payload)
        else:
            payload = json.loads(arguments.input.read_text(encoding="utf-8"))
        records = normalize_records(payload, preserve_hours=True)
        hourly_records = _aggregate_hourly_window_records(records, target_hour)
        if not hourly_records:
            print(
                "No hourly usage records from "
                f"{window_start.isoformat()} to {window_end.isoformat()}; no report written."
            )
            return 0
        hourly_directory = arguments.root / "data" / "hourly"
        history = [record for record in read_records(hourly_directory) if record.usage_hour_utc != target_hour]
        write_hourly_records(hourly_records, hourly_directory)
        prune_hourly_files(hourly_directory, target_hour, max(config.history_days, config.data_retention_days), ".csv")
        all_records = history + hourly_records
        anomalies = detect_hourly_anomalies(all_records, target_hour, config)
        threshold, free_tiers, data_io_free_gb = load_free_tiers(arguments.root / "config" / "free_tiers.json")
        month_records = [
            record for record in all_records
            if record.usage_date.year == target_hour.year and record.usage_date.month == target_hour.month
        ]
        quota_statuses = evaluate_month_to_date(month_records, threshold, free_tiers, data_io_free_gb)
        quota_alerts = [quota for quota in quota_statuses if quota.status == "EXCEEDED"]
        if not anomalies and not quota_alerts:
            notified = notify_webhook([], hourly_records, target_hour.isoformat())
            print(f"No hourly anomaly for {target_hour.isoformat()}; no report written.")
            print(f"Webhook event sent: {'yes' if notified else 'no'}")
            return 0
        report = render_hourly_report(hourly_records, anomalies, quota_alerts)
        report_path = write_hourly_report(report, arguments.root / "reports", target_hour)
        prune_hourly_files(arguments.root / "reports" / "hourly", target_hour, config.report_retention_days, ".md")
        report_reference = str(report_path)
        print(f"Wrote hourly anomaly report: {report_path}")
        notified = notify_webhook(anomalies, hourly_records, report_reference, quota_alerts)
        print(f"Webhook event sent: {'yes' if notified else 'no'}")
        return 0
    config = load_detection_config(arguments.root / "config" / "thresholds.json")
    if arguments.fetch:
        raw_payload = HereUsageClient().fetch_usage(target_date)
        payload = json.loads(raw_payload)
    else:
        payload = json.loads(arguments.input.read_text(encoding="utf-8"))

    records = normalize_records(payload)
    daily_records = [record for record in records if record.usage_date == target_date]
    if not daily_records:
        raise ValueError(f"Input has no records for {target_date.isoformat()}")
    curated_directory = arguments.root / "data" / "curated"
    history = [record for record in read_records(curated_directory) if record.usage_date != target_date]
    write_daily_records(daily_records, curated_directory)
    prune_daily_files(curated_directory, target_date, max(config.history_days, config.data_retention_days), ".csv")
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
    report_path = write_daily_report(report, arguments.root / "reports", target_date.isoformat())
    prune_daily_files(arguments.root / "reports", target_date, config.report_retention_days, ".md")
    report_reference = str(report_path)
    print(f"Wrote report: {report_path}")
    print(f"Anomalies: {len(anomalies)}")
    notified = notify_webhook(anomalies, daily_records, report_reference, quota_alerts)
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


def _aggregate_hourly_window_records(records: list[UsageRecord], target_hour: datetime) -> list[UsageRecord]:
    target_hour = target_hour.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    aggregated: list[UsageRecord] = []
    record_positions: dict[tuple[str, str, str], int] = {}
    for record in records:
        if record.usage_hour_utc is None:
            continue
        window_record = replace(record, usage_date=target_hour.date(), usage_hour_utc=target_hour)
        unique_key = (window_record.metric, window_record.dimension_key, window_record.unit)
        if unique_key in record_positions:
            position = record_positions[unique_key]
            existing = aggregated[position]
            aggregated[position] = replace(
                existing,
                quantity=existing.quantity + window_record.quantity,
                category=existing.category or window_record.category,
            )
            continue
        record_positions[unique_key] = len(aggregated)
        aggregated.append(window_record)
    return aggregated
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