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
    allowance: float
    percentage: float
    status: str


def load_free_tiers(path: Path) -> tuple[float, dict[str, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return float(payload["approaching_threshold"]), {
        str(metric): float(allowance)
        for metric, allowance in payload["transaction_free_tiers"].items()
    }


def evaluate_month_to_date(
    records: list[UsageRecord], approaching_threshold: float, free_tiers: dict[str, float]
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
        statuses.append(QuotaStatus(metric, usage, allowance, percentage, status))
    return statuses