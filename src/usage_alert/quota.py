from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import UsageRecord


@dataclass(frozen=True)
class QuotaStatus:
    metric: str
    usage: float
    allowance: float | None
    percentage: float | None
    status: str
    unit: str = "Transactions"


def load_free_tiers(path: Path) -> tuple[float, dict[str, float], float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return float(payload["approaching_threshold"]), {
        str(metric): float(allowance)
        for metric, allowance in payload["transaction_free_tiers"].items()
    }, float(payload["data_io_free_gb_months"])


def evaluate_month_to_date(
    records: list[UsageRecord], approaching_threshold: float, free_tiers: dict[str, float], data_io_free_gb: float
) -> list[QuotaStatus]:
    transaction_totals: dict[str, float] = defaultdict(float)
    for record in records:
        if record.unit == "Transactions":
            transaction_totals[record.metric] += record.quantity

    statuses: list[QuotaStatus] = []
    for metric, usage in sorted(transaction_totals.items()):
        allowance = free_tiers.get(metric)
        if allowance is None:
            continue
        percentage = usage / allowance
        status = "EXCEEDED" if percentage >= 1 else "APPROACHING" if percentage >= approaching_threshold else "WITHIN_FREE_TIER"
        statuses.append(QuotaStatus(metric, usage, allowance, percentage, status, "Transactions"))

    data_io_totals: dict[str, float] = defaultdict(float)
    for record in records:
        if record.category in {"DataIO", "DataStorage"}:
            data_io_totals[record.unit] += record.quantity

    gb_months_usage = data_io_totals.get("GB-Months", 0.0)
    gb_months_status = "NOT_REPORTED" if "GB-Months" not in data_io_totals else (
        "EXCEEDED" if gb_months_usage >= data_io_free_gb else
        "APPROACHING" if gb_months_usage / data_io_free_gb >= approaching_threshold else
        "WITHIN_FREE_TIER"
    )
    statuses.append(
        QuotaStatus("Data IO total", gb_months_usage, data_io_free_gb,
                    gb_months_usage / data_io_free_gb, gb_months_status, "GB-Months")
    )
    return statuses