from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import median

from .models import Anomaly, DetectionConfig, UsageRecord


def detect_anomalies(
    records: list[UsageRecord], target_date: date, config: DetectionConfig
) -> list[Anomaly]:
    grouped: dict[tuple[str, str], list[UsageRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.metric, record.dimension_key)].append(record)

    anomalies: list[Anomaly] = []
    for series in grouped.values():
        current = next((record for record in series if record.usage_date == target_date), None)
        if current is None:
            continue
        history = sorted(
            (record.quantity for record in series if record.usage_date < target_date), reverse=True
        )[: config.history_days]
        if len(history) < config.minimum_baseline_days:
            continue
        baseline = median(history)
        absolute_increase = current.quantity - baseline
        percentage_increase = absolute_increase / baseline if baseline else float("inf")
        deviations = [abs(value - baseline) for value in history]
        mad = median(deviations)
        robust_z_score = None if mad == 0 else 0.6745 * absolute_increase / mad
        is_spike = (
            current.quantity >= baseline * (1 + config.percentage_increase_threshold)
            and absolute_increase >= config.minimum_absolute_increase
            and (
                (robust_z_score is not None and robust_z_score >= config.robust_z_score_threshold)
                or (mad == 0 and absolute_increase > 0)
            )
        )
        if not is_spike:
            continue
        severity = (
            "critical"
            if percentage_increase >= config.critical_percentage
            else "warning"
        )
        anomalies.append(
            Anomaly(
                record=current,
                baseline_median=baseline,
                baseline_sample_size=len(history),
                absolute_increase=absolute_increase,
                percentage_increase=percentage_increase,
                robust_z_score=robust_z_score,
                severity=severity,
            )
        )
    return sorted(anomalies, key=lambda anomaly: anomaly.record.quantity, reverse=True)