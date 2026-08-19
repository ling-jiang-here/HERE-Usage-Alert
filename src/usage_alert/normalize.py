from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from .models import UsageRecord


class SchemaError(ValueError):
    """Raised when an input response cannot be mapped safely."""


def normalize_records(payload: Any, retrieved_at: datetime | None = None) -> list[UsageRecord]:
    """Normalize the temporary fixture contract into validated canonical records.

    Replace only this mapper when the redacted HERE Usage API response is available.
    """
    rows = payload.get("records") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SchemaError("Expected a list or an object with a 'records' list")

    timestamp = retrieved_at or datetime.now(timezone.utc)
    records: list[UsageRecord] = []
    seen: set[tuple[date, str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SchemaError(f"Record {index} is not an object")
        try:
            usage_date = date.fromisoformat(str(row["usage_date_utc"]))
            metric = str(row["metric"]).strip()
            quantity = float(row["quantity"])
            unit = str(row["unit"]).strip()
        except (KeyError, TypeError, ValueError) as error:
            raise SchemaError(f"Record {index} has invalid required fields") from error
        if not metric or not unit or quantity < 0:
            raise SchemaError(f"Record {index} has an empty metric/unit or negative quantity")

        dimensions = {
            key: str(row[key]).strip()
            for key in ("feature_id", "app_id", "project_id", "billing_tag")
            if row.get(key) not in (None, "")
        }
        dimension_key = json.dumps(dimensions, sort_keys=True, separators=(",", ":"))
        unique_key = (usage_date, metric, dimension_key)
        if unique_key in seen:
            raise SchemaError(f"Record {index} duplicates a daily usage series")
        seen.add(unique_key)
        records.append(
            UsageRecord(
                usage_date=usage_date,
                metric=metric,
                quantity=quantity,
                unit=unit,
                feature_id=dimensions.get("feature_id"),
                app_id=dimensions.get("app_id"),
                project_id=dimensions.get("project_id"),
                billing_tag=dimensions.get("billing_tag"),
                dimension_key=dimension_key,
                source_retrieved_at=timestamp,
            )
        )
    return records