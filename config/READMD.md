# Threshold Tuning Guide (`thresholds.json`)

This file explains how each parameter in [config/thresholds.json](thresholds.json) affects anomaly detection behavior, and how to tune values safely.

Current defaults:

```json
{
  "history_days": 30,
  "minimum_baseline_days": 14,
  "minimum_absolute_increase": 1000,
  "percentage_increase_threshold": 0.5,
  "robust_z_score_threshold": 3.5,
  "severity": {
    "warning_percentage": 0.5,
    "critical_percentage": 2.0
  }
}
```

## How Detection Works (high level)

A day is considered abnormal only when the increase is both:

1. Large enough in absolute terms (`minimum_absolute_increase`), and
2. Large enough relative to baseline (`percentage_increase_threshold`),

and is statistically unusual (`robust_z_score_threshold`) once enough history is present (`minimum_baseline_days`).

This design helps avoid alerts from tiny-volume noise while still catching real spikes.

## Parameter-by-Parameter Explanation

### `history_days`
- Meaning: How many recent days are loaded for baseline and comparisons.
- Default: `30`
- Increase it when:
  - Your usage has weekly/biweekly patterns and you want more stable context.
- Decrease it when:
  - Your traffic changes quickly and older data is no longer relevant.
- Typical range: `21` to `60`

Example:
- If weekday/weekend behavior is very different, moving from `30` to `45` can stabilize the baseline.

### `minimum_baseline_days`
- Meaning: Minimum number of prior data points required before statistical checks are trusted.
- Default: `14`
- Increase it when:
  - You see early false positives in new environments.
- Decrease it when:
  - You need detection sooner after a new rollout.
- Typical range: `7` to `21`

Example:
- A new realm with only 8 days of data will not use full statistical confidence if this is `14`.
- Setting it to `7` enables earlier detection, but may be noisier.

### `minimum_absolute_increase`
- Meaning: Minimum raw delta required before a rise can be considered abnormal.
- Default: `1000`
- Increase it when:
  - Low-volume services produce noisy alerts from small numeric jumps.
- Decrease it when:
  - You monitor low-traffic services where +200 can already be meaningful.
- Typical range:
  - High volume: `2000` to `10000`
  - Medium volume: `500` to `3000`
  - Low volume: `100` to `1000`

Example:
- Baseline = 400/day, today = 700/day:
  - Absolute increase = `300`
  - With threshold `1000`: no alert.
  - With threshold `200`: this gate passes (other gates still apply).

### `percentage_increase_threshold`
- Meaning: Minimum relative increase over baseline.
- Default: `0.5` (50%)
- Increase it when:
  - You only care about major jumps.
- Decrease it when:
  - You want earlier warning on moderate growth.
- Typical range: `0.3` (30%) to `1.0` (100%)

Formula:
- Relative increase = `(today - baseline) / baseline`

Examples:
- Baseline = 10,000, today = 13,000 -> increase = 30% (`0.3`)
  - Triggers if threshold <= `0.3`
- Baseline = 2,000, today = 3,400 -> increase = 70% (`0.7`)
  - Triggers if threshold <= `0.7`

### `robust_z_score_threshold`
- Meaning: Statistical outlier sensitivity. Lower value = more sensitive.
- Default: `3.5`
- Increase it when:
  - You get alerts on normal variability.
- Decrease it when:
  - You want to catch subtle but unusual movement.
- Typical range: `2.5` to `4.5`

Interpretation:
- `2.5`: aggressive, catches more anomalies (more false positives).
- `3.5`: balanced default.
- `4.5`: conservative, catches only strong outliers.

### `severity.warning_percentage`
- Meaning: Relative increase threshold for classifying a triggered anomaly as warning.
- Default: `0.5` (50%)

### `severity.critical_percentage`
- Meaning: Relative increase threshold for classifying a triggered anomaly as critical.
- Default: `2.0` (200%)

Severity examples:
- Increase = 80% (`0.8`) -> warning (>= 0.5 and < 2.0)
- Increase = 250% (`2.5`) -> critical (>= 2.0)

## Practical Tuning Scenarios

### 1) Too many false positives on low volume
Symptoms:
- Alerts fire on small jumps (for example 50 -> 110).

Try:
- Raise `minimum_absolute_increase` (for example `1000` -> `1500` if units are large).
- Raise `robust_z_score_threshold` (for example `3.5` -> `4.0`).
- Keep `percentage_increase_threshold` moderate (`0.5` to `0.8`).

### 2) Missing important spikes
Symptoms:
- Real incidents are visible in dashboard but no anomaly alert appears.

Try:
- Lower `minimum_absolute_increase` (for example `1000` -> `500`).
- Lower `percentage_increase_threshold` (for example `0.5` -> `0.35`).
- Lower `robust_z_score_threshold` slightly (`3.5` -> `3.0`).

### 3) New service needs earlier protection
Symptoms:
- Detection starts too late after go-live.

Try:
- Lower `minimum_baseline_days` (`14` -> `7`).

Trade-off:
- Earlier detection with less statistical confidence.

### 4) Stable, high-volume production with occasional campaign bursts
Symptoms:
- Planned bursts trigger noisy alerts.

Try:
- Raise `minimum_absolute_increase` and/or `percentage_increase_threshold`.
- Raise `critical_percentage` if only extreme events should page.

## Recommended Starting Presets

### Conservative (fewer alerts)
```json
{
  "minimum_absolute_increase": 2000,
  "percentage_increase_threshold": 0.8,
  "robust_z_score_threshold": 4.0,
  "minimum_baseline_days": 14
}
```

### Balanced (default-like)
```json
{
  "minimum_absolute_increase": 1000,
  "percentage_increase_threshold": 0.5,
  "robust_z_score_threshold": 3.5,
  "minimum_baseline_days": 14
}
```

### Sensitive (catch early changes)
```json
{
  "minimum_absolute_increase": 400,
  "percentage_increase_threshold": 0.3,
  "robust_z_score_threshold": 2.8,
  "minimum_baseline_days": 10
}
```

## Safe Change Process

1. Change only one or two parameters at a time.
2. Run for at least 1 to 2 weeks.
3. Compare:
   - Number of alerts
   - False positives
   - Missed incidents
4. Adjust again in small increments.

Small, measured tuning is usually more reliable than large jumps.
