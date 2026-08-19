from __future__ import annotations

from pathlib import Path

from .models import Anomaly, UsageRecord


def render_daily_report(records: list[UsageRecord], anomalies: list[Anomaly]) -> str:
    usage_date = records[0].usage_date.isoformat() if records else "unknown"
    total = sum(record.quantity for record in records)
    lines = [
        f"# HERE Usage Report: {usage_date}",
        "",
        f"- Usage series: {len(records)}",
        f"- Total quantity: {total:,.0f}",
        f"- Anomalies: {len(anomalies)}",
        "",
        "## Anomalies",
        "",
    ]
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


def write_daily_report(contents: str, directory: Path, usage_date: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    output_path = directory / f"{usage_date}.md"
    output_path.write_text(contents, encoding="utf-8")
    return output_path