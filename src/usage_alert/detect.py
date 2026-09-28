from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
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
        history_records = sorted(
            (record for record in series if record.usage_date < target_date),
            key=lambda r: r.usage_date, reverse=True,
        )[: config.history_days]
        if len(history_records) < config.secondary_min_baseline_days:
            continue
        baseline_source = (
            [r.quantity for r in history_records[: config.baseline_window]]
            if config.baseline_window
            else [r.quantity for r in history_records]
        )
        baseline = median(baseline_source)
        absolute_increase = current.quantity - baseline
        percentage_increase = absolute_increase / baseline if baseline else float("inf")
        deviations = [abs(value - baseline) for value in baseline_source]
        mad = median(deviations)
        robust_z_score = None if mad == 0 else 0.6745 * absolute_increase / mad
        is_spike = False
        if len(history_records) >= config.minimum_baseline_days:
            is_spike = (
                current.quantity >= baseline * (1 + config.percentage_increase_threshold)
                and absolute_increase >= config.minimum_absolute_increase
                and (
                    (robust_z_score is not None and robust_z_score >= config.robust_z_score_threshold)
                    or (mad == 0 and absolute_increase > 0)
                )
            )
        if not is_spike and len(history_records) < config.minimum_baseline_days:
            is_spike = (
                baseline > 0
                and current.quantity >= baseline * config.secondary_spike_multiplier
                and (current.quantity - baseline) >= config.secondary_min_absolute
            )
        if not is_spike and config.weekly_growth_multiplier:
            week_ago = target_date - timedelta(days=7)
            week_ago_record = next(
                (r for r in series if r.usage_date == week_ago), None
            )
            if week_ago_record and week_ago_record.quantity > 0:
                growth_ratio = current.quantity / week_ago_record.quantity
                growth_absolute = current.quantity - week_ago_record.quantity
                if (growth_ratio >= config.weekly_growth_multiplier
                        and growth_absolute >= config.weekly_growth_min_absolute):
                    is_spike = True
                    absolute_increase = growth_absolute
                    percentage_increase = absolute_increase / week_ago_record.quantity
                    baseline = week_ago_record.quantity
                    baseline_source = [week_ago_record.quantity]
                    mad = 0
                    robust_z_score = None
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
                baseline_sample_size=len(history_records),
                absolute_increase=absolute_increase,
                percentage_increase=percentage_increase,
                robust_z_score=robust_z_score,
                severity=severity,
            )
        )
    return sorted(anomalies, key=lambda anomaly: anomaly.record.quantity, reverse=True)


def detect_hourly_anomalies(
    records: list[UsageRecord], target_hour_utc: datetime, config: DetectionConfig
) -> list[Anomaly]:
    """Compare the completed hour with the same UTC hour on prior days."""
    target_hour_utc = target_hour_utc.replace(minute=0, second=0, microsecond=0)
    grouped: dict[tuple[str, str], list[UsageRecord]] = defaultdict(list)
    for record in records:
        if record.usage_hour_utc is not None:
            grouped[(record.metric, record.dimension_key)].append(record)

    anomalies: list[Anomaly] = []
    for series in grouped.values():
        current = next((record for record in series if record.usage_hour_utc == target_hour_utc), None)
        if current is None:
            continue
        history_records = sorted(
            (record for record in series
             if record.usage_hour_utc < target_hour_utc
             and record.usage_hour_utc.hour == target_hour_utc.hour),
            key=lambda r: r.usage_hour_utc, reverse=True,
        )[: config.history_days]
        if len(history_records) < config.secondary_min_baseline_days:
            continue
        baseline_source = (
            [r.quantity for r in history_records[: config.baseline_window]]
            if config.baseline_window
            else [r.quantity for r in history_records]
        )
        baseline = median(baseline_source)
        absolute_increase = current.quantity - baseline
        percentage_increase = absolute_increase / baseline if baseline else float("inf")
        mad = median(abs(value - baseline) for value in baseline_source)
        robust_z_score = None if mad == 0 else 0.6745 * absolute_increase / mad
        is_spike = False
        if len(history_records) >= config.minimum_baseline_days:
            is_spike = (
                current.quantity >= baseline * (1 + config.percentage_increase_threshold)
                and absolute_increase >= config.minimum_absolute_increase
                and ((robust_z_score is not None and robust_z_score >= config.robust_z_score_threshold)
                     or (mad == 0 and absolute_increase > 0))
            )
        if not is_spike and len(history_records) < config.minimum_baseline_days:
            is_spike = (
                baseline > 0
                and current.quantity >= baseline * config.secondary_spike_multiplier
                and (current.quantity - baseline) >= config.secondary_min_absolute
            )
        if not is_spike and config.weekly_growth_multiplier:
            week_ago = (target_hour_utc - timedelta(days=7)).date()
            week_ago_record = next(
                (r for r in series
                 if r.usage_hour_utc and r.usage_hour_utc.date() == week_ago
                 and r.usage_hour_utc.hour == target_hour_utc.hour),
                None,
            )
            if week_ago_record and week_ago_record.quantity > 0:
                growth_ratio = current.quantity / week_ago_record.quantity
                growth_absolute = current.quantity - week_ago_record.quantity
                if (growth_ratio >= config.weekly_growth_multiplier
                        and growth_absolute >= config.weekly_growth_min_absolute):
                    is_spike = True
                    absolute_increase = growth_absolute
                    percentage_increase = absolute_increase / week_ago_record.quantity
                    baseline = week_ago_record.quantity
                    baseline_source = [week_ago_record.quantity]
                    mad = 0
                    robust_z_score = None
        if not is_spike:
            continue
        anomalies.append(Anomaly(
            record=current, baseline_median=baseline, baseline_sample_size=len(history_records),
            absolute_increase=absolute_increase, percentage_increase=percentage_increase,
            robust_z_score=robust_z_score,
            severity="critical" if percentage_increase >= config.critical_percentage else "warning",
        ))
    return sorted(anomalies, key=lambda anomaly: anomaly.record.quantity, reverse=True)