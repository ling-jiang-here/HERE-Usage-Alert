from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timezone
from typing import Any

from .models import UsageRecord


class SchemaError(ValueError):
    """Raised when an input response cannot be mapped safely."""


def normalize_records(payload: Any, retrieved_at: datetime | None = None) -> list[UsageRecord]:
    """Normalize the temporary fixture contract into validated canonical records.

    Replace only this mapper when the redacted HERE Usage API response is available.
    """
    rows = payload.get("items", payload.get("records")) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SchemaError("Expected a list or an object with a 'records' list")

    timestamp = retrieved_at or datetime.now(timezone.utc)
    records: list[UsageRecord] = []
    record_positions: dict[tuple[date, str, str], int] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SchemaError(f"Record {index} is not an object")
        try:
            usage_date = date.fromisoformat(str(_first_value(row, "usage_date_utc", "usageDateTime"))[:10])
            metric = str(_first_value(row, "metric", "name", "featureId")).strip()
            quantity = float(_first_value(row, "quantity", "billableValue", "usageValue"))
            unit = str(_first_value(row, "unit", "valueDriver", default="usage")).strip()
        except (KeyError, TypeError, ValueError) as error:
            raise SchemaError(f"Record {index} has invalid required fields") from error
        if not metric or not unit or quantity < 0:
            raise SchemaError(f"Record {index} has an empty metric/unit or negative quantity")

        dimensions = {}
        for key, candidates in (
            ("feature_id", ("feature_id", "featureId")),
            ("app_id", ("app_id", "appId")),
            ("project_id", ("project_id", "projectHrn")),
            ("billing_tag", ("billing_tag", "billingTag")),
        ):
            value = _first_value(row, *candidates, default=None)
            if value not in (None, ""):
                dimensions[key] = str(value).strip()
        dimension_key = json.dumps(dimensions, sort_keys=True, separators=(",", ":"))
        unique_key = (usage_date, metric, dimension_key)
        category = _first_value(row, "category", default=None)
        if unique_key in record_positions:
            position = record_positions[unique_key]
            existing = records[position]
            if existing.unit != unit:
                raise SchemaError(f"Record {index} duplicates a daily usage series with a conflicting unit")
            records[position] = replace(
                existing,
                quantity=existing.quantity + quantity,
                category=existing.category or category,
            )
            continue
        record_positions[unique_key] = len(records)
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
                category=category,
            )
        )
    return records


def _first_value(row: dict[str, Any], *keys: str, default: Any = ...) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    if default is not ...:
        return default
    raise KeyError(keys[0])