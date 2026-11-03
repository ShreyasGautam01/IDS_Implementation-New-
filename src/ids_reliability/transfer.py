from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score, matthews_corrcoef
from sklearn.model_selection import train_test_split

from .config import AppConfig
from .data_audit import clean_row_validity
from .features import select_features
from .io import iter_table_chunks, sha256_file
from .model import KnownClassClassifier
from .preprocessing import TrainOnlyPreprocessor
from .splitting import create_global_temporal_split


class TransferExperimentError(RuntimeError):
    pass


def _load_binary_disjoint_samples(
    path: str | Path,
    label_column: str,
    source_sample_size: int,
    target_sample_size: int,
    seed: int,
    chunk_rows: int = 250_000,
    duration_substring: str = "DURATION",
    packet_columns: tuple[str, ...] = ("IN_PKTS", "OUT_PKTS"),
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Stream a dataset and draw two disjoint, deterministic uniform samples.

    Each cleaned row receives an independent random priority. Retaining the top
    k priorities over all chunks is an exact uniform k-row sample without
    replacement. Sorting the retained priorities creates a random permutation;
    the first source-sized block and next target-sized block are disjoint.
    The same samples are reused for all model seeds.
    """
    if source_sample_size <= 0 or target_sample_size <= 0:
        raise TransferExperimentError("Source and target sample sizes must be positive")
    if chunk_rows <= 0:
        raise TransferExperimentError("transfer chunk row count must be positive")

    source_path = Path(path).expanduser().resolve()
    keep_count = source_sample_size + target_sample_size
    rng = np.random.default_rng(seed)
    reservoir = pd.DataFrame()
    reservoir_keys = np.empty(0, dtype=float)
    raw_rows = 0
    clean_rows = 0
    chunk_count = 0
    audit_totals = {
        "missing_label_rows_removed": 0,
        "blank_label_rows_removed": 0,
        "negative_duration_rows_removed": 0,
        "zero_or_missing_packet_rows_removed": 0,
    }
    duration_columns_checked: set[str] = set()
    packet_columns_checked: set[str] = set()
    expected_columns: set[str] | None = None

    for chunk in iter_table_chunks(source_path, batch_rows=chunk_rows):
        chunk_count += 1
        chunk_columns = set(str(column) for column in chunk.columns)
        if expected_columns is None:
            expected_columns = chunk_columns
        elif chunk_columns != expected_columns:
            raise TransferExperimentError(
                f"Dataset schema changed between streamed chunks in {source_path}; "
                f"missing={sorted(expected_columns - chunk_columns)}, "
                f"unexpected={sorted(chunk_columns - expected_columns)}"
            )
        raw_rows += len(chunk)
        if label_column not in chunk.columns:
            raise TransferExperimentError(f"Binary label column {label_column!r} is missing from {source_path}")
        clean, audit = clean_row_validity(
            chunk,
            label_column,
            duration_substring=duration_substring,
            packet_columns=packet_columns,
            allow_empty=True,
        )
        clean_rows += len(clean)
        for key in audit_totals:
            audit_totals[key] += int(audit[key])
        duration_columns_checked.update(audit["duration_columns_checked"])
        packet_columns_checked.update(audit["packet_columns_checked"])
        if clean.empty:
            continue
        binary = pd.to_numeric(clean[label_column], errors="coerce")
        if binary.isna().any() or not np.isin(binary.to_numpy(dtype=float), [0.0, 1.0]).all():
            raise TransferExperimentError(
                f"Cross-dataset experiment requires a valid binary 0/1 label column; invalid values found in {source_path}"
            )
        clean["__target__"] = binary.astype(int)
        keys = rng.random(len(clean))
        # Keep only this chunk's top priorities before concatenation. Combining
        # the complete chunk with the reservoir creates large transient copies
        # on multi-million-row Parquet files.
        local_count = min(keep_count, len(clean))
        if len(clean) > local_count:
            local_indices = np.argpartition(keys, -local_count)[-local_count:]
            clean = clean.iloc[local_indices].reset_index(drop=True)
            keys = keys[local_indices]
        if len(reservoir):
            candidates = pd.concat([reservoir, clean], ignore_index=True)
            candidate_keys = np.concatenate([reservoir_keys, keys])
        else:
            candidates = clean.reset_index(drop=True)
            candidate_keys = keys
        if len(candidates) > keep_count:
            selected = np.argpartition(candidate_keys, -keep_count)[-keep_count:]
            reservoir = candidates.iloc[selected].reset_index(drop=True)
            reservoir_keys = candidate_keys[selected]
        else:
            reservoir = candidates.reset_index(drop=True)
            reservoir_keys = candidate_keys
        if chunk_count % 10 == 0:
            print(
                f"Sampled {raw_rows:,} rows from {source_path.name} "
                f"({chunk_count} chunks)...",
                flush=True,
            )

    if raw_rows == 0 or clean_rows == 0:
        raise TransferExperimentError(f"No valid rows were read from {source_path}")
    if len(reservoir) < 4:
        raise TransferExperimentError(
            f"Only {len(reservoir)} valid rows remain in {source_path}; at least four are needed for disjoint binary samples"
        )

    # If the dataset is smaller than the requested combined sample, use two
    # balanced, disjoint subsets rather than reuse observations across roles.
    actual_target_size = min(target_sample_size, len(reservoir) // 2)
    actual_source_size = min(source_sample_size, len(reservoir) - actual_target_size)
    if actual_source_size < 2 or actual_target_size < 2:
        raise TransferExperimentError("Not enough valid rows for two disjoint samples with at least two observations each")
    order = np.argsort(-reservoir_keys, kind="stable")
    ordered = reservoir.iloc[order].reset_index(drop=True)
    source_sample = ordered.iloc[:actual_source_size].copy().reset_index(drop=True)
    target_sample = ordered.iloc[actual_source_size:actual_source_size + actual_target_size].copy().reset_index(drop=True)

    for name, sample in (("source", source_sample), ("target", target_sample)):
        if set(sample["__target__"].astype(int).unique()) != {0, 1}:
            raise TransferExperimentError(
                f"Fixed {name} sample for {source_path} does not contain both binary classes; "
                "increase the sample size or define a predeclared stratified sampling design"
            )

    audit_result: dict[str, object] = {
        "source_path": str(source_path),
        "raw_rows_streamed": int(raw_rows),
        "valid_rows_after_physical_filters": int(clean_rows),
        "removed_rows": int(raw_rows - clean_rows),
        "chunk_count": int(chunk_count),
        "schema_columns": sorted(expected_columns or set()),
        **audit_totals,
        "duration_columns_checked": sorted(duration_columns_checked),
        "packet_columns_checked": sorted(packet_columns_checked),
        "deduplication": "not_performed",
        "sampling_method": "streamed independent random priorities; top-k exact uniform sample without replacement",
        "source_sample_rows": int(len(source_sample)),
        "target_sample_rows": int(len(target_sample)),
        "samples_disjoint": True,
        "sample_seed": int(seed),
        "chunk_rows": int(chunk_rows),
    }
    return source_sample, target_sample, audit_result


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "mcc": float(matthews_corrcoef(y_true, y_pred)),
    }


def _one_direction(
    source: pd.DataFrame,
    target: pd.DataFrame,
    config: AppConfig,
    schema: str,
    seed: int,
    source_name: str,
    target_name: str,
) -> dict[str, object]:
    label_column = str(config.dataset.get("binary_label_column", "Label"))
    timestamp_column = str(config.dataset["timestamp_column"])
    end_timestamp_column = config.dataset.get("end_timestamp_column")
    selection = select_features(
        source,
        label_columns=[label_column, str(config.dataset.get("label_column", "Attack"))],
        timestamp_column=timestamp_column,
        schema_level=schema,
        end_timestamp_column=(str(end_timestamp_column) if end_timestamp_column else None),
        groups=config.features["groups"],
        identifiers=list(config.features["identifiers"]),
    )
    missing = set(selection.columns).difference(target.columns)
    if missing:
        raise TransferExperimentError(f"Target {target_name} is missing source model features: {sorted(missing)}")
    temporal_split = timestamp_column in source.columns
    if temporal_split:
        split = create_global_temporal_split(
            source,
            timestamp_column=timestamp_column,
            end_timestamp_column=(str(end_timestamp_column) if end_timestamp_column else None),
            end_numeric_timestamp_unit=str(config.dataset.get("end_numeric_timestamp_unit", config.dataset.get("numeric_timestamp_unit", "ms"))),
            numeric_timestamp_unit=str(config.dataset.get("numeric_timestamp_unit", "ms")),
            train_fraction=float(config.split["train_fraction"]),
            validation_fraction=float(config.split["validation_fraction"]),
            calibration_fraction=float(config.split["calibration_fraction"]),
            embargo_seconds=float(config.split.get("embargo_seconds", 0.0)),
            require_unknown_in_test=False,
        )
        train_frame, test_frame = split.train, split.test
        split_boundaries = split.boundaries
        split_strategy = "global_temporal"
    else:
        train_frame, test_frame = train_test_split(
            source,
            train_size=float(config.split["train_fraction"]),
            random_state=1703,
            stratify=source["__target__"],
        )
        train_frame = train_frame.reset_index(drop=True)
        test_frame = test_frame.reset_index(drop=True)
        split_boundaries = None
        split_strategy = "stratified_random_no_timestamp_available"
    train_y = train_frame["__target__"].to_numpy(dtype=int)
    if set(np.unique(train_y)) != {0, 1}:
        raise TransferExperimentError(f"Source training window for {source_name} does not contain both binary classes")
    processor = TrainOnlyPreprocessor(selection.columns, float(config.features.get("clip_limit", 1e15)))
    x_train = processor.fit_transform(train_frame)
    x_source_test = processor.transform(test_frame)
    x_target = processor.transform(target)
    model = KnownClassClassifier(random_state=seed, **dict(config.model.get("parameters", {}))).fit(x_train, train_y)
    source_test_y = test_frame["__target__"].to_numpy(dtype=int)
    target_y = target["__target__"].to_numpy(dtype=int)
    if set(np.unique(source_test_y)) != {0, 1}:
        raise TransferExperimentError(
            f"Source temporal test window for {source_name} does not contain both binary classes"
        )
    if set(np.unique(target_y)) != {0, 1}:
        raise TransferExperimentError(
            f"Fixed target evaluation sample for {target_name} does not contain both binary classes"
        )
    source_pred = model.predict(x_source_test)
    target_pred = model.predict(x_target)
    return {
        "source": source_name,
        "target": target_name,
        "schema": schema,
        "features": len(selection.columns),
        "seed": seed,
        "source_train_rows": len(train_frame),
        "source_test_rows": len(test_frame),
        "source_split_strategy": split_strategy,
        "target_evaluation_rows": len(target),
        "source_train_class_counts": {str(k): int(v) for k, v in pd.Series(train_y).value_counts().sort_index().items()},
        "source_test_class_counts": {str(k): int(v) for k, v in test_frame["__target__"].value_counts().sort_index().items()},
        "target_class_counts": {str(k): int(v) for k, v in target["__target__"].value_counts().sort_index().items()},
        "source_in_domain": _metrics(source_test_y, source_pred),
        "zero_shot_target": _metrics(target_y, target_pred),
        "selected_feature_names": list(selection.columns),
        "split_boundaries": split_boundaries,
    }


def run_cross_dataset_experiment(config: AppConfig, source_a_path: str | Path, source_b_path: str | Path, seeds: list[int] | None = None) -> Path:
    label_column = str(config.dataset.get("binary_label_column", "Label"))
    a_path, b_path = Path(source_a_path).resolve(), Path(source_b_path).resolve()

    # Stream each dataset once and retain two disjoint fixed samples. This avoids
    # loading the ~20-million-row CIC18-v3 file into memory merely to sample it.
    source_limit = int(config.dataset.get("transfer_source_sample_size", 200_000))
    target_limit = int(config.dataset.get("transfer_target_sample_size", 200_000))
    chunk_rows = int(config.dataset.get("transfer_chunk_rows", 250_000))
    seed_a = int(config.dataset.get("transfer_sample_seed_dataset_a", 1701))
    seed_b = int(config.dataset.get("transfer_sample_seed_dataset_b", 1702))
    packet_columns = tuple(config.dataset.get("packet_columns", ["IN_PKTS", "OUT_PKTS"]))
    duration_substring = str(config.dataset.get("duration_substring", "DURATION"))

    a_source, a_target, cleaning_audit_a = _load_binary_disjoint_samples(
        a_path, label_column, source_limit, target_limit, seed_a, chunk_rows,
        duration_substring, packet_columns,
    )
    b_source, b_target, cleaning_audit_b = _load_binary_disjoint_samples(
        b_path, label_column, source_limit, target_limit, seed_b, chunk_rows,
        duration_substring, packet_columns,
    )

    seeds = seeds or list(config.model.get("transfer_seeds", [42, 43, 44, 45]))
    results: list[dict[str, object]] = []
    for schema in ("baseline", "set_a", "set_b", "set_c"):
        for seed in seeds:
            results.append(_one_direction(a_source, b_target, config, schema, int(seed), "dataset_A", "dataset_B"))
            results.append(_one_direction(b_source, a_target, config, schema, int(seed), "dataset_B", "dataset_A"))

    rows = []
    for item in results:
        flat = {k: v for k, v in item.items() if k not in {"source_in_domain", "zero_shot_target", "selected_feature_names", "split_boundaries"}}
        for key in ("source_train_class_counts", "source_test_class_counts", "target_class_counts"):
            if key in flat:
                flat[key] = json.dumps(flat[key], sort_keys=True)
        for phase in ("source_in_domain", "zero_shot_target"):
            for metric, value in item[phase].items():
                flat[f"{phase}_{metric}"] = value
        rows.append(flat)
    output = Path(config.output["directory"]).expanduser().resolve() / "cross_dataset"
    output.mkdir(parents=True, exist_ok=True)
    detail = pd.DataFrame(rows)
    detail.to_csv(output / "cross_dataset_per_seed.csv", index=False)
    group_columns = ["source", "target", "schema", "features"]
    metric_columns = [c for c in detail.columns if c.startswith("source_in_domain_") or c.startswith("zero_shot_target_")]
    summary = detail.groupby(group_columns, as_index=False)[metric_columns].agg(["mean", "std", "min", "max"])
    summary.columns = ["_".join(str(x) for x in col if x) if isinstance(col, tuple) else col for col in summary.columns]
    summary.to_csv(output / "cross_dataset_summary.csv", index=False)
    metadata = {
        "experiment": "binary_bidirectional_cross_dataset_feature_ablation",
        "seeds": seeds,
        "declared_dataset_release": config.dataset.get("release", "unspecified"),
        "source_sample_size_limit": source_limit,
        "target_sample_size_limit": target_limit,
        "source_sample_rows_dataset_a": int(len(a_source)),
        "source_sample_rows_dataset_b": int(len(b_source)),
        "target_sample_rows_dataset_a": int(len(a_target)),
        "target_sample_rows_dataset_b": int(len(b_target)),
        "source_and_target_samples_fixed_across_model_seeds": True,
        "sample_seed_dataset_a": seed_a,
        "sample_seed_dataset_b": seed_b,
        "chunk_rows": chunk_rows,
        "samples_disjoint_within_each_dataset": True,
        "cleaning_audit_dataset_a": cleaning_audit_a,
        "cleaning_audit_dataset_b": cleaning_audit_b,
        "sample_class_counts": {
            "dataset_A_source": {str(k): int(v) for k, v in a_source["__target__"].value_counts().sort_index().items()},
            "dataset_A_target": {str(k): int(v) for k, v in a_target["__target__"].value_counts().sort_index().items()},
            "dataset_B_source": {str(k): int(v) for k, v in b_source["__target__"].value_counts().sort_index().items()},
            "dataset_B_target": {str(k): int(v) for k, v in b_target["__target__"].value_counts().sort_index().items()},
        },
        "per_run_protocol": [
            {
                "source": item["source"],
                "target": item["target"],
                "schema": item["schema"],
                "seed": item["seed"],
                "feature_names": item["selected_feature_names"],
                "split_boundaries": item["split_boundaries"],
                "source_train_rows": item["source_train_rows"],
                "source_test_rows": item["source_test_rows"],
                "source_split_strategy": item["source_split_strategy"],
                "target_evaluation_rows": item["target_evaluation_rows"],
            }
            for item in results
        ],
        "source_a": {"path": str(a_path), "sha256": sha256_file(a_path)},
        "source_b": {"path": str(b_path), "sha256": sha256_file(b_path)},
        "sampling_note": "Each dataset is streamed once; deterministic disjoint source/target samples are drawn using random priorities and reused across all model seeds.",
        "note": "This is a separate binary transfer experiment; it does not evaluate the complete OSR-conformal-SOC system.",
    }
    (output / "experiment_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output
