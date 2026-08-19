from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from .client import HereUsageClient
from .config import load_detection_config, load_dotenv
from .detect import detect_anomalies
from .notify import notify_webhook
from .normalize import normalize_records
from .report import render_daily_report, write_daily_report
from .storage import read_records, write_daily_records, write_raw_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor HERE organization usage for daily anomalies.")
    parser.add_argument("--date", type=date.fromisoformat, help="Completed UTC usage date (YYYY-MM-DD).")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Recorded JSON response using the temporary fixture contract.")
    source.add_argument("--fetch", action="store_true", help="Fetch a live response using the configured HERE client.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Project root for data and reports.")
    arguments = parser.parse_args()

    load_dotenv(arguments.root / ".env")
    target_date = arguments.date or date.today() - timedelta(days=1)
    if arguments.fetch:
        raw_payload = HereUsageClient().fetch_usage(target_date)
        write_raw_artifact(raw_payload, arguments.root / "artifacts" / "raw", target_date.isoformat())
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
    all_records = history + daily_records
    config = load_detection_config(arguments.root / "config" / "thresholds.json")
    anomalies = detect_anomalies(all_records, target_date, config)
    report = render_daily_report(daily_records, anomalies)
    report_path = write_daily_report(report, arguments.root / "reports", target_date.isoformat())
    notified = notify_webhook(anomalies, str(report_path))
    print(f"Wrote report: {report_path}")
    print(f"Anomalies: {len(anomalies)}")
    print(f"Webhook alert sent: {'yes' if notified else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())