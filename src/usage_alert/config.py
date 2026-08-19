from __future__ import annotations

import json
import os
from pathlib import Path

from .models import DetectionConfig


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load simple KEY=VALUE entries without logging their values."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_detection_config(path: Path) -> DetectionConfig:
    payload = json.loads(path.read_text(encoding="utf-8"))
    severity = payload["severity"]
    return DetectionConfig(
        history_days=int(payload["history_days"]),
        minimum_baseline_days=int(payload["minimum_baseline_days"]),
        minimum_absolute_increase=float(payload["minimum_absolute_increase"]),
        percentage_increase_threshold=float(payload["percentage_increase_threshold"]),
        robust_z_score_threshold=float(payload["robust_z_score_threshold"]),
        warning_percentage=float(severity["warning_percentage"]),
        critical_percentage=float(severity["critical_percentage"]),
    )