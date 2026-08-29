from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .models import Anomaly, UsageRecord
from .quota import QuotaStatus


def render_daily_report(
    records: list[UsageRecord], anomalies: list[Anomaly], quota_statuses: list[QuotaStatus] | None = None,
    remediation_note: str | None = None,
) -> str:
    usage_date = records[0].usage_date.isoformat() if records else "unknown"
    usage_summary = summarize_usage(records)
    lines = [
        f"# HERE Usage Report: {usage_date}",
        "",
        f"- Usage series: {len(usage_summary)}",
        f"- Anomalies: {len(anomalies)}",
        "",
        "## Usage By Unit And Metric",
        "",
        "| Unit | Metric | Quantity |",
        "| --- | --- | ---: |",
    ]
    for unit, metric, quantity in usage_summary:
        lines.append(f"| {unit} | {metric} | {format_quantity(quantity)} |")
    lines.extend([
        "",
        "## Month-To-Date Free-Tier Status",
        "",
    ])
    if not quota_statuses:
        lines.append("No transaction usage matched a configured free-tier service for this month.")
    else:
        lines.extend([
            "| Service | MTD Usage | Free Allowance | Used | Status |",
            "| --- | ---: | ---: | ---: | --- |",
        ])
        for quota in quota_statuses:
            allowance = f"{format_quantity(quota.allowance)} {quota.unit}" if quota.allowance is not None else "N/A"
            percentage = f"{quota.percentage:.1%}" if quota.percentage is not None else "N/A"
            lines.append(
                f"| {quota.metric} | {format_quantity(quota.usage)} {quota.unit} | {allowance} | "
                f"{percentage} | {quota.status} |"
            )
    lines.extend([
        "",
        "Transaction services and Data IO totals are evaluated only against matching free-tier units. "
        "DataStorage records are included as Data IO usage; non-comparable units remain in the usage summary only.",
        "",
    ])
    if remediation_note:
        lines.extend([
            "## Remediation Advisory",
            "",
            remediation_note,
            "",
        ])
    lines.extend([
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


def format_quantity(quantity: float) -> str:
    precision = 4 if 0 < abs(quantity) < 1 else 2
    return f"{quantity:,.{precision}f}"


def write_daily_report(contents: str, directory: Path, usage_date: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / f"{usage_date}.md"
    output_path.write_text(contents, encoding="utf-8")
    return output_path


def render_hourly_report(
    records: list[UsageRecord], anomalies: list[Anomaly], quota_alerts: list[QuotaStatus] | None = None,
    remediation_note: str | None = None,
) -> str:
    usage_hour = records[0].usage_hour_utc.isoformat() if records and records[0].usage_hour_utc else "unknown"
    lines = [f"# HERE Usage Anomaly: {usage_hour}", "", f"- Anomalies: {len(anomalies)}", ""]
    quota_alerts = quota_alerts or []
    for anomaly in anomalies:
        lines.append(
            f"- **{anomaly.severity.upper()}** {anomaly.record.metric} "
            f"({anomaly.record.feature_id or '-'} / {anomaly.record.app_id or '-'}): "
            f"{anomaly.record.quantity:,.2f} vs {anomaly.baseline_median:,.2f} baseline "
            f"({anomaly.percentage_increase:+.0%})"
        )
    if quota_alerts:
        lines.extend(["", "## Free-Tier Alerts", ""])
        for quota in quota_alerts:
            percentage = f"{quota.percentage:.1%}" if quota.percentage is not None else "N/A"
            lines.append(
                f"- **{quota.status}** {quota.metric}: {format_quantity(quota.usage)} {quota.unit} "
                f"against {format_quantity(quota.allowance or 0)} {quota.unit} ({percentage})"
            )
    if remediation_note:
        lines.extend(["", "## Remediation Advisory", "", remediation_note])
    return "\n".join(lines) + "\n"


def write_hourly_report(contents: str, directory: Path, usage_hour: datetime) -> Path:
    output_directory = directory / "hourly"
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"{usage_hour.strftime('%Y-%m-%dT%H')}Z.md"
    output_path.write_text(contents, encoding="utf-8")
    return output_path