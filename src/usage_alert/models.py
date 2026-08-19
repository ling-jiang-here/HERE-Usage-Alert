from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class UsageRecord:
    usage_date: date
    metric: str
    quantity: float
    unit: str
    feature_id: str | None
    app_id: str | None
    project_id: str | None
    billing_tag: str | None
    dimension_key: str
    source_retrieved_at: datetime


@dataclass(frozen=True)
class DetectionConfig:
    history_days: int
    minimum_baseline_days: int
    minimum_absolute_increase: float
    percentage_increase_threshold: float
    robust_z_score_threshold: float
    warning_percentage: float
    critical_percentage: float


@dataclass(frozen=True)
class Anomaly:
    record: UsageRecord
    baseline_median: float
    baseline_sample_size: int
    absolute_increase: float
    percentage_increase: float
    robust_z_score: float | None
    severity: str