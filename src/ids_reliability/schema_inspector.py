from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

from .config import AppConfig


class SchemaInspectionError(RuntimeError):
    pass


def _parse_time(values: pd.Series, unit: str) -> pd.Series:
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_datetime(values, unit=unit, utc=True, errors="coerce")
    return pd.to_datetime(values, utc=True, errors="coerce", format="mixed")


def inspect_dataset_schema(
    path: str | Path,
    config: AppConfig,
    sample_rows: int = 1000,
) -> dict[str, object]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise SchemaInspectionError(f"Dataset file does not exist: {source}")
    if sample_rows <= 0:
        raise SchemaInspectionError("sample_rows must be positive")

    time_col = str(config.dataset["timestamp_column"])
    label_col = str(config.dataset["label_column"])
    end_col_value = config.dataset.get("end_timestamp_column")
    end_col = str(end_col_value) if end_col_value else None
    required = [time_col, label_col] + ([end_col] if end_col else [])

    suffix = source.suffix.casefold()
    if suffix in {".parquet", ".pq"}:
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise SchemaInspectionError("Install pyarrow to inspect Parquet schemas") from exc
        parquet = pq.ParquetFile(source)
        raw_names = list(parquet.schema_arrow.names)
        normalized_names = [str(name).strip() for name in raw_names]
        if len(normalized_names) != len(set(normalized_names)):
            raise SchemaInspectionError("Parquet columns collide after trimming whitespace")
        raw_by_normalized = dict(zip(normalized_names, raw_names))
        available_normalized = [column for column in required if column in raw_by_normalized]
        available_raw = [raw_by_normalized[column] for column in available_normalized]
        sample_table = (
            parquet.read_row_group(0, columns=available_raw)
            if parquet.num_row_groups and available_raw
            else None
        )
        sample = (
            sample_table.to_pandas().head(sample_rows)
            if sample_table is not None
            else pd.DataFrame(columns=available_raw)
        )
        if sample_table is not None:
            sample.columns = [str(column).strip() for column in sample.columns]
        names = normalized_names
        type_map = {
            str(field.name).strip(): str(field.type) for field in parquet.schema_arrow
        }
        row_count: int | None = int(parquet.metadata.num_rows)
        source_format = "parquet"
    elif suffix == ".csv" or source.name.casefold().endswith(".csv.gz"):
        sample = pd.read_csv(source, nrows=sample_rows, low_memory=False)
        sample.columns = [str(column).strip() for column in sample.columns]
        if sample.columns.duplicated().any():
            raise SchemaInspectionError("CSV columns collide after trimming whitespace")
        names = [str(column) for column in sample.columns]
        type_map = {str(column): str(dtype) for column, dtype in sample.dtypes.items()}
        row_count = None
        source_format = "csv"
    else:
        raise SchemaInspectionError(f"Unsupported file extension: {source.suffix}")

    missing = [column for column in required if column not in names]
    timestamp_summary: dict[str, object] = {
        "column": time_col,
        "present": time_col in names,
    }
    if time_col in sample.columns:
        parsed = _parse_time(
            sample[time_col], str(config.dataset.get("numeric_timestamp_unit", "ms"))
        )
        timestamp_summary.update(
            {
                "sample_valid": int(parsed.notna().sum()),
                "sample_invalid": int(parsed.isna().sum()),
                "sample_min_utc": parsed.min().isoformat() if parsed.notna().any() else None,
                "sample_max_utc": parsed.max().isoformat() if parsed.notna().any() else None,
                "configured_numeric_unit": config.dataset.get("numeric_timestamp_unit", "ms"),
            }
        )

    interval_summary: dict[str, object] = {
        "end_column": end_col,
        "complete_flow_interval_checked": False,
    }
    if end_col and end_col in sample.columns and time_col in sample.columns:
        start_parsed = _parse_time(
            sample[time_col], str(config.dataset.get("numeric_timestamp_unit", "ms"))
        )
        end_parsed = _parse_time(
            sample[end_col],
            str(
                config.dataset.get(
                    "end_numeric_timestamp_unit",
                    config.dataset.get("numeric_timestamp_unit", "ms"),
                )
            ),
        )
        valid_interval = start_parsed.notna() & end_parsed.notna()
        interval_summary.update(
            {
                "complete_flow_interval_checked": True,
                "valid_intervals": int(valid_interval.sum()),
                "invalid_start_or_end": int((~valid_interval).sum()),
                "end_before_start": int(
                    (valid_interval & (end_parsed < start_parsed)).sum()
                ),
                "sample_max_duration_seconds": (
                    float((end_parsed[valid_interval] - start_parsed[valid_interval]).dt.total_seconds().max())
                    if valid_interval.any()
                    else None
                ),
            }
        )

    label_summary: dict[str, object] = {"column": label_col, "present": label_col in names}
    if label_col in sample.columns:
        label_summary["sample_counts"] = {
            str(k): int(v)
            for k, v in sample[label_col].value_counts(dropna=False).items()
        }

    timestamp_sample_valid = timestamp_summary.get("sample_valid", 0) == len(sample)
    interval_sample_valid = (
        end_col is None
        or (
            interval_summary.get("complete_flow_interval_checked")
            and interval_summary.get("invalid_start_or_end") == 0
            and interval_summary.get("end_before_start") == 0
        )
    )
    return {
        "path": str(source),
        "format": source_format,
        "full_row_count_from_metadata": row_count,
        "columns": names,
        "column_types": type_map,
        "sample_rows_read": int(len(sample)),
        "required_columns": required,
        "required_columns_missing": missing,
        "timestamp": timestamp_summary,
        "label": label_summary,
        "flow_interval": interval_summary,
        "temporal_ready_sample_check": bool(
            not missing and len(sample) > 0 and timestamp_sample_valid and interval_sample_valid
        ),
        "warning": (
            "Sample inspection verifies column presence and sample parsing only; it does not "
            "replace the full data audit or independently validate timestamp semantics."
        ),
    }


def write_schema_report(report: dict[str, object], output_path: str | Path) -> Path:
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return destination
