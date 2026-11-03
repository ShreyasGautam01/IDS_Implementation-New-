from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd


class DataAuditError(ValueError):
    pass


def clean_row_validity(
    frame: pd.DataFrame,
    label_column: str,
    duration_substring: str = "DURATION",
    packet_columns: tuple[str, ...] = ("IN_PKTS", "OUT_PKTS"),
    allow_empty: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Remove only explicit pointwise-invalid rows; never deduplicate.

    Column headers are stripped before lookup. Blank string labels are treated
    as missing. Numeric coercion is used only for physical-validity checks;
    feature conversion/imputation remains the responsibility of the train-only
    preprocessor.
    """
    work = frame.copy()
    work.columns = [str(column).strip() for column in work.columns]
    if work.columns.duplicated().any():
        duplicates = work.columns[work.columns.duplicated()].tolist()
        raise DataAuditError(f"Column names collide after whitespace normalization: {duplicates}")
    if label_column not in work:
        raise DataAuditError(f"Label column {label_column!r} is missing")

    initial = len(work)
    label_values = work[label_column]
    blank_label = label_values.map(lambda value: isinstance(value, str) and not value.strip())
    missing_label = label_values.isna()
    missing_label_rows = int(missing_label.sum())
    blank_label_rows = int(blank_label.sum())
    work = work.loc[~(missing_label | blank_label)].copy()
    work[label_column] = work[label_column].map(
        lambda value: value.strip() if isinstance(value, str) else value
    )

    duration_cols = [
        column
        for column in work.columns
        if duration_substring.casefold() in column.casefold()
    ]
    negative_duration_mask = pd.Series(False, index=work.index)
    for column in duration_cols:
        duration_values = pd.to_numeric(work[column], errors="coerce")
        negative_duration_mask |= duration_values < 0
    negative_duration_rows = int(negative_duration_mask.sum())
    work = work.loc[~negative_duration_mask].copy()

    column_lookup = {column.casefold(): column for column in work.columns}
    packet_actual = [column_lookup.get(name.casefold()) for name in packet_columns]
    packet_actual = [column for column in packet_actual if column is not None]
    zero_packet_rows = 0
    if len(packet_actual) == len(packet_columns):
        packet_values = work[packet_actual].apply(pd.to_numeric, errors="coerce")
        packet_sum = packet_values.sum(axis=1, min_count=len(packet_actual))
        zero_mask = packet_sum.isna() | (packet_sum <= 0)
        zero_packet_rows = int(zero_mask.sum())
        work = work.loc[~zero_mask].copy()

    audit = {
        "input_rows": int(initial),
        "missing_label_rows_removed": missing_label_rows,
        "blank_label_rows_removed": blank_label_rows,
        "negative_duration_rows_removed": negative_duration_rows,
        "zero_or_missing_packet_rows_removed": zero_packet_rows,
        "rows_after_physical_validity_filters": int(len(work)),
        "rows_removed_total": int(initial - len(work)),
        "duration_columns_checked": duration_cols,
        "packet_columns_checked": packet_actual,
        "deduplication": "not_performed; duplicate overlap is audited separately",
    }
    if work.empty and not allow_empty:
        raise DataAuditError("No rows remain after physically invalid row filtering")
    return work.reset_index(drop=True), audit


def dataset_audit(
    frame: pd.DataFrame,
    label_column: str,
    timestamp_column: str,
    duplicate_sample_size: int = 200_000,
    seed: int = 17,
    end_timestamp_column: str | None = None,
    numeric_timestamp_unit: str = "ms",
    end_numeric_timestamp_unit: str | None = None,
) -> dict[str, Any]:
    if frame.empty:
        raise DataAuditError("Cannot audit an empty dataset")
    if duplicate_sample_size <= 0:
        raise DataAuditError("duplicate_sample_size must be positive")
    if label_column not in frame:
        raise DataAuditError(f"Label column {label_column!r} is missing")
    if timestamp_column not in frame:
        raise DataAuditError(f"Timestamp column {timestamp_column!r} is missing")
    sample = (
        frame
        if len(frame) <= duplicate_sample_size
        else frame.sample(n=duplicate_sample_size, random_state=seed)
    )
    numeric_frame = frame.select_dtypes(include=[np.number])
    nonfinite_counts = {
        str(column): int((~np.isfinite(numeric_frame[column].to_numpy(dtype=float, copy=False))).sum())
        for column in numeric_frame.columns
        if (~np.isfinite(numeric_frame[column].to_numpy(dtype=float, copy=False))).any()
    }

    start_values = frame[timestamp_column]
    start_parsed = (
        pd.to_datetime(start_values, unit=numeric_timestamp_unit, utc=True, errors="coerce")
        if pd.api.types.is_numeric_dtype(start_values)
        else pd.to_datetime(start_values, utc=True, errors="coerce")
    )
    timestamp_audit: dict[str, Any] = {
        "start_column": timestamp_column,
        "start_missing_values": int(start_values.isna().sum()),
        "start_unparseable_values": int(start_parsed.isna().sum()),
        "start_min_utc": start_parsed.min().isoformat() if start_parsed.notna().any() else None,
        "start_max_utc": start_parsed.max().isoformat() if start_parsed.notna().any() else None,
    }
    if end_timestamp_column:
        if end_timestamp_column not in frame:
            raise DataAuditError(f"Flow end-time column {end_timestamp_column!r} is missing")
        end_values = frame[end_timestamp_column]
        end_unit = end_numeric_timestamp_unit or numeric_timestamp_unit
        end_parsed = (
            pd.to_datetime(end_values, unit=end_unit, utc=True, errors="coerce")
            if pd.api.types.is_numeric_dtype(end_values)
            else pd.to_datetime(end_values, utc=True, errors="coerce")
        )
        valid_interval = start_parsed.notna() & end_parsed.notna()
        timestamp_audit.update(
            {
                "end_column": end_timestamp_column,
                "end_missing_values": int(end_values.isna().sum()),
                "end_unparseable_values": int(end_parsed.isna().sum()),
                "end_before_start_rows": int(
                    (valid_interval & (end_parsed < start_parsed)).sum()
                ),
                "complete_interval_parse_valid_rows": int(valid_interval.sum()),
                "max_flow_duration_seconds": (
                    float((end_parsed[valid_interval] - start_parsed[valid_interval]).dt.total_seconds().max())
                    if valid_interval.any()
                    else None
                ),
            }
        )

    return {
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "column_names": [str(column) for column in frame.columns],
        "label_counts": {
            str(key): int(value)
            for key, value in frame[label_column].value_counts(dropna=False).items()
        },
        "missing_labels": int(frame[label_column].isna().sum()),
        "nonfinite_numeric_values_by_column": nonfinite_counts,
        "numeric_columns": [str(column) for column in numeric_frame.columns],
        "timestamp_audit": timestamp_audit,
        "duplicate_audit": {
            "method": "exact duplicate count on deterministic sample"
            if len(sample) < len(frame)
            else "exact full-table duplicate count",
            "sample_rows": int(len(sample)),
            "sample_duplicate_rows": int(sample.duplicated().sum()),
            "sample_fraction": float(len(sample) / len(frame)),
            "note": "Sample count is not extrapolated to the full dataset.",
        },
    }
