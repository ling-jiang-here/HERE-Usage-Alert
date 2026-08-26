from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

from .models import UsageRecord


HEADERS = (
    "usage_date_utc", "metric", "quantity", "unit", "feature_id", "app_id",
    "project_id", "billing_tag", "category", "dimension_key", "source_retrieved_at_utc", "usage_hour_utc",
)


def write_daily_records(records: list[UsageRecord], directory: Path) -> Path:
    if not records:
        raise ValueError("Cannot persist an empty usage dataset")
    dates = {record.usage_date for record in records}
    if len(dates) != 1:
        raise ValueError("A daily output must contain one usage date")
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / f"{next(iter(dates)).isoformat()}.csv"
    temporary_path = output_path.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, lineterminator="\n")
        writer.writeheader()
        for record in sorted(records, key=lambda item: (item.metric, item.dimension_key)):
            writer.writerow({
                "usage_date_utc": record.usage_date.isoformat(),
                "metric": record.metric,
                "quantity": record.quantity,
                "unit": record.unit,
                "feature_id": record.feature_id or "",
                "app_id": record.app_id or "",
                "project_id": record.project_id or "",
                "billing_tag": record.billing_tag or "",
                "category": record.category or "",
                "dimension_key": record.dimension_key,
                "source_retrieved_at_utc": record.source_retrieved_at.isoformat(),
                "usage_hour_utc": record.usage_hour_utc.isoformat() if record.usage_hour_utc else "",
            })
    os.replace(temporary_path, output_path)
    return output_path


def read_records(directory: Path) -> list[UsageRecord]:
    if not directory.exists():
        return []
    records: list[UsageRecord] = []
    for path in sorted(directory.glob("*.csv")):
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                records.append(UsageRecord(
                    usage_date=datetime.fromisoformat(row["usage_date_utc"]).date(),
                    metric=row["metric"], quantity=float(row["quantity"]), unit=row["unit"],
                    feature_id=row["feature_id"] or None, app_id=row["app_id"] or None,
                    project_id=row["project_id"] or None, billing_tag=row["billing_tag"] or None,
                    dimension_key=row["dimension_key"],
                    source_retrieved_at=datetime.fromisoformat(row["source_retrieved_at_utc"]),
                    category=row.get("category") or None,
                    usage_hour_utc=(
                        datetime.fromisoformat(row["usage_hour_utc"])
                        if row.get("usage_hour_utc") else None
                    ),
                ))
    return records


def write_hourly_records(records: list[UsageRecord], directory: Path) -> Path:
    if not records or any(record.usage_hour_utc is None for record in records):
        raise ValueError("Hourly output requires records with a UTC hour")
    hours = {record.usage_hour_utc for record in records}
    if len(hours) != 1:
        raise ValueError("An hourly output must contain one UTC hour")
    directory.mkdir(parents=True, exist_ok=True)
    hour = next(iter(hours))
    output_path = directory / f"{hour.strftime('%Y-%m-%dT%H')}Z.csv"
    temporary_path = output_path.with_suffix(".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, lineterminator="\n")
        writer.writeheader()
        for record in sorted(records, key=lambda item: (item.metric, item.dimension_key)):
            writer.writerow({
                "usage_date_utc": record.usage_date.isoformat(), "metric": record.metric,
                "quantity": record.quantity, "unit": record.unit,
                "feature_id": record.feature_id or "", "app_id": record.app_id or "",
                "project_id": record.project_id or "", "billing_tag": record.billing_tag or "",
                "category": record.category or "", "dimension_key": record.dimension_key,
                "source_retrieved_at_utc": record.source_retrieved_at.isoformat(),
                "usage_hour_utc": record.usage_hour_utc.isoformat(),
            })
    os.replace(temporary_path, output_path)
    return output_path

