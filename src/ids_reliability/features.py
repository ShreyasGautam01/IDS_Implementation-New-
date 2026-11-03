from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import pandas as pd


class FeatureSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class FeatureSelection:
    columns: tuple[str, ...]
    removed_by_group: dict[str, tuple[str, ...]]
    absent_configured_columns: dict[str, tuple[str, ...]]
    nonnumeric_columns: tuple[str, ...]


def select_features(
    frame: pd.DataFrame,
    label_columns: Iterable[str],
    timestamp_column: str,
    schema_level: str,
    groups: dict[str, list[str]],
    identifiers: list[str],
    end_timestamp_column: str | None = None,
) -> FeatureSelection:
    if schema_level not in {"baseline", "set_a", "set_b", "set_c"}:
        raise FeatureSchemaError(f"Unsupported feature schema: {schema_level}")
    excluded = {str(x).casefold() for x in label_columns}
    excluded.update({timestamp_column.casefold(), "__target__", "__timestamp_utc__", "__flow_end_utc__"})
    if end_timestamp_column:
        excluded.add(end_timestamp_column.casefold())
    excluded.update(str(x).casefold() for x in identifiers)
    group_order = ["ttl", "window", "protocol"]
    source_columns_by_casefold = {str(c).casefold(): str(c) for c in frame.columns}
    active = {
        "baseline": set(),
        "set_a": {"ttl"},
        "set_b": {"ttl", "window"},
        "set_c": {"ttl", "window", "protocol"},
    }[schema_level]
    removed: dict[str, tuple[str, ...]] = {}
    absent: dict[str, tuple[str, ...]] = {}
    for group in group_order:
        configured = list(groups.get(group, []))
        present = tuple(source_columns_by_casefold[c.casefold()] for c in configured if c.casefold() in source_columns_by_casefold)
        missing = tuple(c for c in configured if c.casefold() not in source_columns_by_casefold)
        removed[group] = present if group in active else tuple()
        absent[group] = missing
        if group in active:
            excluded.update(c.casefold() for c in present)
    candidate = [c for c in frame.columns if c.casefold() not in excluded]
    numeric = [c for c in candidate if pd.api.types.is_numeric_dtype(frame[c])]
    nonnumeric = [c for c in candidate if c not in numeric]
    if nonnumeric:
        raise FeatureSchemaError(
            "Unexpected non-numeric predictor columns require an explicit encoding policy; "
            f"not silently dropping them: {nonnumeric}"
        )
    if not numeric:
        raise FeatureSchemaError("No numeric predictor columns remain after feature selection")
    return FeatureSelection(
        columns=tuple(numeric),
        removed_by_group=removed,
        absent_configured_columns=absent,
        nonnumeric_columns=tuple(nonnumeric),
    )
