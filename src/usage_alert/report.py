from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .models import Anomaly, UsageRecord
from .quota import QuotaStatus


def render_daily_report(
    records: list[UsageRecord], anomalies: list[Anomaly], quota_statuses: list[QuotaStatus] | None = None
) -> str:
    usage_date = records[0].usage_date.isoformat() if records else "unknown"
    lines = [
        f"# HERE Usage Report: {usage_date}",
        "",
        f"- Usage series: {len(records)}",
        f"- Anomalies: {len(anomalies)}",
        "",
        "## Usage By Unit And Metric",
        "",
        "| Unit | Metric | Quantity |",
        "| --- | --- | ---: |",
    ]
    for unit, metric, quantity in summarize_usage(records):
        lines.append(f"| {unit} | {metric} | {quantity:,.2f} |")
    lines.extend([
        "",
        "## Month-To-Date Free-Tier Status",
        "",
    ])
    if not quota_statuses:
        lines.append("No transaction usage matched a configured free-tier service for this month.")
    else:
        lines.extend([
            "| Service | MTD Transactions | Free Allowance | Used | Status |",
            "| --- | ---: | ---: | ---: | --- |",
        ])
        for quota in quota_statuses:
            lines.append(
                f"| {quota.metric} | {quota.usage:,.0f} | {quota.allowance:,.0f} | "
                f"{quota.percentage:.1%} | {quota.status} |"
            )
    lines.extend([
        "",
        "Only transaction-based services with configured public free tiers are evaluated. "
        "Storage and data units are not combined with transaction allowances.",
        "",
        "## Anomalies",
        "",
    ])
    if not anomalies:
        lines.append("No anomaly met the configured threshold.")
    else:
        lines.extend([
            "| Severity | Metric | Feature | App | Observed | Baseline | Change | Evidence |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
        ])
        for anomaly in anomalies:
            score = "zero-MAD rule" if anomaly.robust_z_score is None else f"z={anomaly.robust_z_score:.2f}"
            lines.append(
                "| {severity} | {metric} | {feature} | {app} | {observed:,.0f} | "
                "{baseline:,.0f} | {change:+.0%} | {score}; n={sample_size} |".format(
                    severity=anomaly.severity.upper(), metric=anomaly.record.metric,
                    feature=anomaly.record.feature_id or "-", app=anomaly.record.app_id or "-",
                    observed=anomaly.record.quantity, baseline=anomaly.baseline_median,
                    change=anomaly.percentage_increase, score=score,
                    sample_size=anomaly.baseline_sample_size,
                )
            )
        lines.extend([
            "",
            "Hypotheses are unverified. Review deployments, retry behavior, and caching telemetry.",
        ])
    return "\n".join(lines) + "\n"


def summarize_usage(records: list[UsageRecord]) -> list[tuple[str, str, float]]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for record in records:
        totals[(record.unit, record.metric)] += record.quantity
    return [
        (unit, metric, quantity)
        for (unit, metric), quantity in sorted(totals.items(), key=lambda item: (item[0][0], item[0][1]))
    ]


def write_daily_report(contents: str, directory: Path, usage_date: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / f"{usage_date}.md"
    output_path.write_text(contents, encoding="utf-8")
    return output_path