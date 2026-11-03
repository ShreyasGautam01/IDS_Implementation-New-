from __future__ import annotations

from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import f1_score, recall_score

from .config import AppConfig
from .data_audit import clean_row_validity
from .features import select_features
from .io import load_table, sha256_file
from .preprocessing import TrainOnlyPreprocessor
from .splitting import create_global_temporal_split


class MonotonicityExperimentError(RuntimeError):
    pass


def run_binary_monotonicity_experiment(config: AppConfig, dataset_path: str | Path | None = None, seed: int | None = None) -> Path:
    """Separate binary-only volumetric sensitivity experiment.

    This does not modify or imply a monotonicity guarantee for the multiclass
    OSR/conformal/triage pipeline.
    """
    path = Path(dataset_path or config.dataset["path"]).expanduser().resolve()
    label_col = str(config.dataset.get("binary_label_column", "Label"))
    time_col = str(config.dataset["timestamp_column"])
    frame, cleaning = clean_row_validity(load_table(path), label_col)
    y = pd.to_numeric(frame[label_col], errors="coerce")
    if y.isna().any() or not set(y.astype(int).unique()).issubset({0, 1}):
        raise MonotonicityExperimentError("Monotonic sensitivity experiment requires binary Label values 0 and 1")
    frame["__target__"] = y.astype(int)
    selection = select_features(
        frame,
        label_columns=[label_col, str(config.dataset.get("label_column", "Attack"))],
        timestamp_column=time_col,
        schema_level=str(config.features["schema_level"]).casefold(),
        end_timestamp_column=(str(config.dataset["end_timestamp_column"]) if config.dataset.get("end_timestamp_column") else None),
        groups=config.features["groups"],
        identifiers=list(config.features["identifiers"]),
    )
    keyword_set = tuple(str(x).upper() for x in config.features.get("monotonic_volume_keywords", ["BYTES", "PKTS", "THROUGHPUT"]))
    volume_columns = [c for c in selection.columns if any(k in c.upper() for k in keyword_set)]
    if not volume_columns:
        raise MonotonicityExperimentError(f"No selected feature matches configured volumetric keywords {keyword_set}")

    split = create_global_temporal_split(
        frame, timestamp_column=time_col,
        end_timestamp_column=(str(config.dataset["end_timestamp_column"]) if config.dataset.get("end_timestamp_column") else None),
        end_numeric_timestamp_unit=str(config.dataset.get("end_numeric_timestamp_unit", config.dataset.get("numeric_timestamp_unit", "ms"))),
        numeric_timestamp_unit=str(config.dataset.get("numeric_timestamp_unit", "ms")),
        train_fraction=float(config.split["train_fraction"]),
        validation_fraction=float(config.split["validation_fraction"]),
        calibration_fraction=float(config.split["calibration_fraction"]),
        embargo_seconds=float(config.split.get("embargo_seconds", 0.0)),
        require_unknown_in_test=False,
    )
    train_raw = split.train.loc[:, selection.columns].to_numpy(dtype=float)
    test_raw = split.test.loc[:, selection.columns].to_numpy(dtype=float)
    y_train = split.train["__target__"].to_numpy(dtype=int)
    y_test = split.test["__target__"].to_numpy(dtype=int)
    if set(np.unique(y_train)) != {0, 1} or set(np.unique(y_test)) != {0, 1}:
        raise MonotonicityExperimentError("Both binary classes must occur in training and locked test periods")

    processor = TrainOnlyPreprocessor(selection.columns, float(config.features.get("clip_limit", 1e15)))
    processor.fit(split.train)
    volume_indices = np.array([selection.columns.index(c) for c in volume_columns], dtype=int)
    train_imputed_raw = processor.imputer.transform(train_raw)
    iqr = np.subtract(
        *np.percentile(train_imputed_raw[:, volume_indices], [75, 25], axis=0)
    )
    iqr = np.where(np.isfinite(iqr) & (iqr > 0), iqr, 1.0)

    augmentation_fraction = float(config.raw.get("monotonicity", {}).get("benign_augmentation_fraction", 0.05))
    augmentation_iqr = float(config.raw.get("monotonicity", {}).get("benign_augmentation_iqr", 6.0))
    rng = np.random.default_rng(int(seed if seed is not None else config.model["random_state"]))
    benign_indices = np.where(y_train == 0)[0]
    n_aug = int(np.floor(len(benign_indices) * augmentation_fraction))
    augmented_raw = train_raw.copy()
    augmented_y = y_train.copy()
    if n_aug > 0:
        chosen = rng.choice(benign_indices, size=n_aug, replace=False)
        elephant = train_raw[chosen].copy()
        elephant[:, volume_indices] += augmentation_iqr * iqr
        augmented_raw = np.vstack([augmented_raw, elephant])
        augmented_y = np.concatenate([augmented_y, np.zeros(n_aug, dtype=int)])

    x_augmented = processor.scaler.transform(processor.imputer.transform(augmented_raw))
    params = dict(config.model.get("parameters", {}))
    random_state = int(seed if seed is not None else config.model["random_state"])
    unconstrained = HistGradientBoostingClassifier(random_state=random_state, early_stopping=False, **params)
    monotonic_vector = [1 if c in volume_columns else 0 for c in selection.columns]
    constrained = HistGradientBoostingClassifier(random_state=random_state, early_stopping=False, monotonic_cst=monotonic_vector, **params)
    unconstrained.fit(x_augmented, augmented_y)
    constrained.fit(x_augmented, augmented_y)

    attack_mask = y_test == 1
    benign_mask = y_test == 0
    rows = []
    epsilons = [
        float(value)
        for value in config.raw.get("monotonicity", {}).get(
            "epsilon_values", [0.0, 0.25, 0.5, 0.75, 1.0]
        )
    ]
    if not epsilons or epsilons[0] < 0 or any(
        right <= left for left, right in zip(epsilons, epsilons[1:])
    ):
        raise MonotonicityExperimentError(
            "epsilon_values must be a strictly increasing sequence of nonnegative values"
        )
    for epsilon in epsilons:
        shifted_raw = test_raw.copy()
        shifted_raw[np.ix_(attack_mask, volume_indices)] += float(epsilon) * augmentation_iqr * iqr
        x_shifted = processor.scaler.transform(processor.imputer.transform(shifted_raw))
        for name, model in (("unconstrained", unconstrained), ("monotone_binary", constrained)):
            prediction = model.predict(x_shifted)
            rows.append({
                "epsilon": float(epsilon),
                "model": name,
                "attack_recall": float(recall_score(y_test[attack_mask], prediction[attack_mask], zero_division=0)),
                "benign_false_positive_rate": float(np.mean(prediction[benign_mask] == 1)),
                "macro_f1": float(f1_score(y_test, prediction, average="macro", zero_division=0)),
                "test_rows": int(len(y_test)),
                "attack_rows": int(attack_mask.sum()),
                "benign_rows": int(benign_mask.sum()),
            })

    # Empirically check each constrained feature independently. Increasing all
    # constrained features simultaneously could hide a violation in one feature
    # behind a larger change in another, so each coordinate is varied separately.
    sample_n = min(1000, len(test_raw))
    audit_indices = np.linspace(0, len(test_raw) - 1, sample_n, dtype=int)
    audit_raw = test_raw[audit_indices].copy()
    positive_column = int(np.where(constrained.classes_ == 1)[0][0])
    feature_audit_rows: list[dict[str, object]] = []
    violations_total = 0
    comparisons_total = 0
    worst_negative_step = 0.0
    for local_col, feature_name in zip(volume_indices, volume_columns):
        probability_levels = []
        for epsilon in epsilons:
            shifted = audit_raw.copy()
            shifted[:, local_col] += epsilon * augmentation_iqr * iqr[
                np.where(volume_indices == local_col)[0][0]
            ]
            x_shifted = processor.scaler.transform(
                processor.imputer.transform(shifted)
            )
            probability_levels.append(
                constrained.predict_proba(x_shifted)[:, positive_column]
            )
        probability_matrix = np.vstack(probability_levels)
        differences = np.diff(probability_matrix, axis=0)
        violations = int(np.sum(differences < -1e-8))
        comparisons = int(differences.size)
        minimum_step = float(np.min(differences)) if differences.size else 0.0
        violations_total += violations
        comparisons_total += comparisons
        worst_negative_step = min(worst_negative_step, minimum_step)
        feature_audit_rows.append(
            {
                "feature": feature_name,
                "tested_rows": sample_n,
                "epsilon_steps": len(epsilons) - 1,
                "monotonicity_comparisons": comparisons,
                "negative_probability_steps_below_tolerance": violations,
                "minimum_probability_step": minimum_step,
                "tolerance": 1e-8,
            }
        )
    feature_audit = pd.DataFrame(feature_audit_rows)
    output = Path(config.output["directory"]).expanduser().resolve() / "monotonicity_binary"
    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "binary_monotonicity_sensitivity.csv", index=False)
    feature_audit.to_csv(output / "monotonicity_feature_audit.csv", index=False)
    metadata = {
        "experiment": "separate_binary_monotonicity_sensitivity",
        "source_dataset": str(path),
        "source_sha256": sha256_file(path),
        "cleaning_audit": cleaning,
        "schema": str(config.features["schema_level"]),
        "selected_features": list(selection.columns),
        "monotonic_features": volume_columns,
        "monotonic_constraints": monotonic_vector,
        "training_augmentation": {
            "benign_fraction": augmentation_fraction,
            "increase_per_volumetric_feature_in_train_iqr": augmentation_iqr,
            "augmented_rows": n_aug,
        },
        "test_perturbation": {
            "epsilon_values": list(epsilons),
            "increase_per_volumetric_feature_in_train_iqr": augmentation_iqr,
            "applied_only_to_attack_test_rows_for_sensitivity_table": True,
        },
        "monotonicity_audit": {
            "method": "each constrained feature independently increased on the same deterministic locked-test subset",
            "tested_rows_per_feature": sample_n,
            "features_tested": volume_columns,
            "total_comparisons": comparisons_total,
            "negative_probability_steps_below_tolerance": violations_total,
            "minimum_probability_step_observed": worst_negative_step,
            "tolerance": 1e-8,
            "details_file": "monotonicity_feature_audit.csv",
        },
        "scope_warning": "Binary sensitivity experiment only; not a guarantee for the multiclass main pipeline or real adversarial robustness.",
    }
    (output / "experiment_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return output
