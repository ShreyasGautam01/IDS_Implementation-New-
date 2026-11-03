import pandas as pd

from ids_reliability.config import AppConfig
from ids_reliability.schema_inspector import inspect_dataset_schema


def test_schema_inspector_reads_only_csv_sample_and_checks_timestamp(tmp_path):
    path = tmp_path / "tiny.csv"
    pd.DataFrame({
        "FLOW_START_MILLISECONDS": [1_700_000_000_000, 1_700_000_001_000],
        "Attack": ["Benign", "DoS"],
    }).to_csv(path, index=False)
    raw = {
        "dataset": {"path": str(path), "timestamp_column": "FLOW_START_MILLISECONDS", "label_column": "Attack", "numeric_timestamp_unit": "ms"},
        "split": {"train_fraction": .55, "validation_fraction": .15, "calibration_fraction": .15},
        "features": {}, "model": {}, "osr": {"target_known_fpr": .05},
        "conformal": {"alpha": .1}, "triage": {"minimum_margin": .2}, "output": {"directory": str(tmp_path)},
    }
    report = inspect_dataset_schema(path, AppConfig(raw, tmp_path / "config.yaml"), sample_rows=1)
    assert report["sample_rows_read"] == 1
    assert report["required_columns_missing"] == []
    assert report["timestamp"]["sample_valid"] == 1


def test_schema_inspector_flags_unparseable_timestamps(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({
        "FLOW_START_MILLISECONDS": ["not-a-timestamp", "still-not-a-time"],
        "Attack": ["Benign", "DoS"],
    }).to_csv(path, index=False)
    raw = {
        "dataset": {"timestamp_column": "FLOW_START_MILLISECONDS", "label_column": "Attack", "numeric_timestamp_unit": "ms"},
        "split": {"train_fraction": .55, "validation_fraction": .15, "calibration_fraction": .15},
        "features": {}, "model": {}, "osr": {"target_known_fpr": .05},
        "conformal": {"alpha": .1}, "triage": {"minimum_margin": .2}, "output": {},
    }
    report = inspect_dataset_schema(path, AppConfig(raw, tmp_path / "config.yaml"), sample_rows=2)
    assert report["temporal_ready_sample_check"] is False
    assert report["timestamp"]["sample_invalid"] == 2
