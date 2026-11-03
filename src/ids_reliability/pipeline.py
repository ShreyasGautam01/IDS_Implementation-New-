from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import platform
import sys
from typing import Any
import numpy as np
import pandas as pd
import scipy
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score

from .config import AppConfig
from .conformal import MarginalSplitConformalPredictor, MondrianConformalPredictor
from .data_audit import clean_row_validity, dataset_audit
from .features import select_features
from .io import load_table, sha256_file
from .labels import build_label_mapping
from .model import KnownClassClassifier
from .open_set import MahalanobisWeibullDetector
from .preprocessing import TrainOnlyPreprocessor
from .splitting import create_global_temporal_split
from .triage import evaluate_triage


class PipelineError(RuntimeError):
    pass


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(_json_safe(obj), indent=2, sort_keys=True, allow_nan=False), encoding="utf-8")


def run_pipeline(config: AppConfig, dataset_path: str | Path | None = None, seed: int | None = None) -> Path:
    cfg = config.raw
    dataset_path = Path(dataset_path or config.dataset["path"]).expanduser().resolve()
    label_column = str(config.dataset["label_column"])
    timestamp_column = str(config.dataset["timestamp_column"])
    end_timestamp_column = config.dataset.get("end_timestamp_column")
    unknown_family = str(config.dataset["unknown_family"])
    seed = int(seed if seed is not None else config.model["random_state"])
    raw = load_table(dataset_path)
    raw_audit = dataset_audit(
        raw,
        label_column,
        timestamp_column,
        duplicate_sample_size=int(config.dataset.get("duplicate_audit_sample_size", 200_000)),
        seed=int(config.dataset.get("duplicate_audit_sample_seed", 17)),
        end_timestamp_column=(str(end_timestamp_column) if end_timestamp_column else None),
        numeric_timestamp_unit=str(config.dataset.get("numeric_timestamp_unit", "ms")),
        end_numeric_timestamp_unit=str(
            config.dataset.get(
                "end_numeric_timestamp_unit",
                config.dataset.get("numeric_timestamp_unit", "ms"),
            )
        ),
    )
    clean, cleaning_audit = clean_row_validity(
        raw, label_column,
        duration_substring=str(config.dataset.get("duration_substring", "DURATION")),
        packet_columns=tuple(config.dataset.get("packet_columns", ["IN_PKTS", "OUT_PKTS"])),
    )
    mapping = build_label_mapping(clean[label_column], unknown_family, config.dataset.get("benign_aliases", ["Benign", "Normal", "BENIGN", "0"]))
    clean["__target__"] = mapping.encode(clean[label_column])

    selection = select_features(
        clean,
        label_columns=[label_column, str(config.dataset.get("binary_label_column", "Label"))],
        timestamp_column=timestamp_column,
        schema_level=str(config.features["schema_level"]).casefold(),
        end_timestamp_column=(str(end_timestamp_column) if end_timestamp_column else None),
        groups=config.features["groups"],
        identifiers=list(config.features["identifiers"]),
    )
    split = create_global_temporal_split(
        clean,
        timestamp_column=timestamp_column,
        numeric_timestamp_unit=str(config.dataset.get("numeric_timestamp_unit", "ms")),
        end_timestamp_column=(str(end_timestamp_column) if end_timestamp_column else None),
        end_numeric_timestamp_unit=str(config.dataset.get("end_numeric_timestamp_unit", config.dataset.get("numeric_timestamp_unit", "ms"))),
        train_fraction=float(config.split["train_fraction"]),
        validation_fraction=float(config.split["validation_fraction"]),
        calibration_fraction=float(config.split["calibration_fraction"]),
        embargo_seconds=float(config.split.get("embargo_seconds", 0.0)),
    )

    expected_classes = set(mapping.id_to_label).difference({-1})
    observed_train_classes = set(split.train["__target__"].astype(int).unique())
    missing = sorted(expected_classes - observed_train_classes)
    if missing:
        raise PipelineError(f"Known classes absent from training partition: {missing}")

    preprocessor = TrainOnlyPreprocessor(selection.columns, float(config.features.get("clip_limit", 1e15)))
    x_train = preprocessor.fit_transform(split.train)
    x_validation = preprocessor.transform(split.validation)
    x_calibration = preprocessor.transform(split.calibration)
    x_test = preprocessor.transform(split.test)
    y_train = split.train["__target__"].to_numpy(dtype=int)
    y_validation = split.validation["__target__"].to_numpy(dtype=int)
    y_calibration = split.calibration["__target__"].to_numpy(dtype=int)
    y_test = split.test["__target__"].to_numpy(dtype=int)
    if not np.any(y_test >= 0):
        raise PipelineError(
            "The locked test window contains no known-class rows; classification, conformal, "
            "and gate-risk metrics would be undefined"
        )
    unknown_test_rows = int(np.sum(y_test == -1))
    minimum_unknown_test_rows = int(
        config.raw.get("evaluation", {}).get("minimum_unknown_test_rows", 20)
    )
    if unknown_test_rows < minimum_unknown_test_rows:
        raise PipelineError(
            f"The locked test window contains {unknown_test_rows} held-out-family rows; "
            f"the predeclared minimum is {minimum_unknown_test_rows}. Do not interpret "
            "open-set AUROC/AUPR from an underpowered unknown-class sample. Review the "
            "dataset's temporal distribution or predeclare a different evaluation design."
        )

    model_parameters = dict(config.model.get("parameters", {}))
    classifier = KnownClassClassifier(random_state=seed, **model_parameters).fit(x_train, y_train)
    expected_ids = np.array(sorted(expected_classes), dtype=int)
    if not np.array_equal(classifier.classes_, expected_ids):
        raise PipelineError(f"Classifier class order mismatch: estimator={classifier.classes_}, expected={expected_ids}")

    osr = MahalanobisWeibullDetector(
        tail_size=int(config.osr["tail_size"]),
        target_known_fpr=float(config.osr["target_known_fpr"]),
        geometry_fraction=float(config.osr.get("geometry_fraction", 0.70)),
        minimum_validation_group=int(config.osr.get("minimum_validation_group", 20)),
    )
    osr.fit(
        x_train,
        y_train,
        timestamps=split.train["__timestamp_utc__"],
    )
    osr.calibrate_threshold(x_validation, y_validation)
    osr_scores, osr_rejected = osr.reject(x_test)

    # Predeclared tail-size sensitivity: geometry and tail-fit observations are
    # held fixed; only the number of upper-tail distances is changed. Each
    # variant receives its own validation-only rejection threshold. Test metrics
    # are reported as diagnostics and are not used to select the primary size.
    requested_tail_sizes = [
        int(value)
        for value in config.osr.get("tail_size_sensitivity", [osr.tail_size])
    ]
    if osr.tail_size not in requested_tail_sizes:
        requested_tail_sizes.append(osr.tail_size)
    if any(value < 5 for value in requested_tail_sizes):
        raise PipelineError("Every configured OSR tail-size sensitivity value must be at least 5")
    requested_tail_sizes = sorted(set(requested_tail_sizes))
    osr_sensitivity_rows = []
    unknown_test_mask_for_osr = y_test == -1
    known_test_mask_for_osr = y_test >= 0
    for tail_size in requested_tail_sizes:
        detector = (
            osr
            if tail_size == osr.tail_size
            else osr.with_tail_size(tail_size).calibrate_threshold(
                x_validation, y_validation
            )
        )
        if tail_size == osr.tail_size:
            scores_variant, rejected_variant = osr_scores, osr_rejected
        else:
            scores_variant, rejected_variant = detector.reject(x_test)
        if unknown_test_mask_for_osr.any() and known_test_mask_for_osr.any():
            binary_unknown = unknown_test_mask_for_osr.astype(int)
            sensitivity_auroc = float(roc_auc_score(binary_unknown, scores_variant))
            sensitivity_aupr = float(average_precision_score(binary_unknown, scores_variant))
        else:
            sensitivity_auroc = float("nan")
            sensitivity_aupr = float("nan")
        osr_sensitivity_rows.append(
            {
                "tail_size_requested": tail_size,
                "tail_size_used_min": min(tail.tail_count for tail in detector.tails_.values()),
                "tail_size_used_max": max(tail.tail_count for tail in detector.tails_.values()),
                "validation_threshold_fit_rejection_rate": detector.validation_threshold_fit_rejection_rate_,
                "locked_test_known_rejection_rate": float(rejected_variant[known_test_mask_for_osr].mean()) if known_test_mask_for_osr.any() else float("nan"),
                "locked_test_unknown_rejection_rate": float(rejected_variant[unknown_test_mask_for_osr].mean()) if unknown_test_mask_for_osr.any() else float("nan"),
                "locked_test_unknown_auroc": sensitivity_auroc,
                "locked_test_unknown_aupr": sensitivity_aupr,
                "locked_test_unknown_prevalence": float(unknown_test_mask_for_osr.mean()),
                "primary_configured_tail_size": tail_size == osr.tail_size,
            }
        )
    osr_sensitivity = pd.DataFrame(osr_sensitivity_rows)
    osr_tail_diagnostics = osr.tail_fit_diagnostics()

    p_cal = classifier.predict_proba(x_calibration)
    p_test = classifier.predict_proba(x_test)
    alpha = float(config.conformal["alpha"])
    conformal = MondrianConformalPredictor(alpha=alpha)
    conformal.fit(p_cal, y_calibration, class_ids=classifier.classes_)
    prediction_sets, evidence_margin, p_values = conformal.predict(p_test)

    marginal = MarginalSplitConformalPredictor(alpha=alpha)
    marginal.fit(p_cal, y_calibration, class_ids=classifier.classes_)
    marginal_sets = marginal.predict(p_test)

    # Compare both methods on exactly the same known-class test observations.
    known_test_mask = y_test >= 0
    true_columns = np.array([int(np.where(classifier.classes_ == y)[0][0]) for y in y_test[known_test_mask]], dtype=int)
    known_indices = np.where(known_test_mask)[0]
    conformal_rows = []
    conformal_class_rows = []
    for method_name, candidate_sets in (("marginal", marginal_sets), ("mondrian", prediction_sets)):
        covered = candidate_sets[known_indices, true_columns]
        set_sizes = candidate_sets[known_indices].sum(axis=1)
        class_coverages = []
        for class_id in classifier.classes_:
            class_mask = y_test == class_id
            class_col = int(np.where(classifier.classes_ == class_id)[0][0])
            coverage = float(candidate_sets[class_mask, class_col].mean()) if class_mask.any() else float("nan")
            class_coverages.append(coverage)
            conformal_class_rows.append({
                "method": method_name,
                "class_id": int(class_id),
                "class": mapping.id_to_label[int(class_id)],
                "support": int(class_mask.sum()),
                "empirical_coverage": coverage,
            })
        finite_coverages = [v for v in class_coverages if np.isfinite(v)]
        conformal_rows.append({
            "method": method_name,
            "alpha": alpha,
            "target_marginal_coverage": 1.0 - alpha,
            "known_test_rows": int(len(known_indices)),
            "overall_known_test_coverage": float(np.mean(covered)),
            "mean_class_coverage": float(np.mean(finite_coverages)),
            "std_across_classes": float(np.std(finite_coverages, ddof=0)),
            "worst_class_coverage": float(np.min(finite_coverages)),
            "mean_prediction_set_size": float(np.mean(set_sizes)),
            "empty_prediction_sets": int(np.sum(set_sizes == 0)),
            "calibration_size": marginal.calibration_size_ if method_name == "marginal" else int(sum(conformal.stratum_sizes_.values())),
        })
    conformal_comparison = pd.DataFrame(conformal_rows)
    conformal_per_class = pd.DataFrame(conformal_class_rows)

    flow_predictions, per_class_metrics, global_metrics, risk_curve = evaluate_triage(
        probabilities=p_test,
        prediction_sets=prediction_sets,
        evidence_margin=evidence_margin,
        osr_scores=osr_scores,
        osr_rejected=osr_rejected,
        y_true=y_test,
        class_ids=classifier.classes_,
        id_to_label=mapping.id_to_label,
        minimum_margin=float(config.triage["minimum_margin"]),
    )
    # Include a compact, inspectable representation of each candidate label's p-value.
    for column, class_id in enumerate(classifier.classes_):
        flow_predictions[f"p_value_class_{int(class_id)}"] = p_values[:, column]

    output_root = Path(config.output["directory"]).expanduser().resolve()
    run_name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_seed{seed}"
    run_dir = output_root / run_name
    run_dir.mkdir(parents=True, exist_ok=False)
    flow_predictions.to_csv(run_dir / "test_predictions.csv", index=False)
    per_class_metrics.to_csv(run_dir / "per_class_metrics.csv", index=False)
    risk_curve.to_csv(run_dir / "risk_coverage_curve.csv", index=False)
    conformal_comparison.to_csv(run_dir / "conformal_comparison.csv", index=False)
    conformal_per_class.to_csv(run_dir / "conformal_per_class_comparison.csv", index=False)
    osr_sensitivity.to_csv(run_dir / "osr_tail_size_sensitivity.csv", index=False)
    osr_tail_diagnostics.to_csv(run_dir / "osr_tail_fit_diagnostics.csv", index=False)

    data_file_metadata = {
        "path": str(dataset_path),
        "size_bytes": int(dataset_path.stat().st_size),
        "sha256": sha256_file(dataset_path) if bool(config.dataset.get("compute_sha256", True)) else None,
    }
    run_metadata = {
        "project_version": "2.0.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "dataset_release_declared_in_config": config.dataset.get("release", "unspecified"),
        "dataset_file": data_file_metadata,
        "raw_dataset_audit": raw_audit,
        "cleaning_audit": cleaning_audit,
        "label_mapping": {"label_to_id": mapping.label_to_id, "id_to_label": mapping.id_to_label, "held_out_family": mapping.unknown_label},
        "feature_selection": {
            "schema_level": config.features["schema_level"],
            "selected_columns": list(selection.columns),
            "selected_count": len(selection.columns),
            "removed_by_group": selection.removed_by_group,
            "configured_but_absent": selection.absent_configured_columns,
        },
        "temporal_split": {"boundaries": split.boundaries, "summary": split.summary},
        "preprocessing": preprocessor.audit_,
        "classifier": {
            "estimator": "HistGradientBoostingClassifier",
            "parameters": model_parameters,
            "classes": classifier.classes_.tolist(),
            "probabilities_calibrated": False,
            "early_stopping": False,
        },
        "open_set": {
            "method": "class_conditional_mahalanobis_weibull_tail_score",
            "tail_size": osr.tail_size,
            "target_known_fpr": osr.target_known_fpr,
            "geometry_fraction_within_proper_training": osr.geometry_fraction,
            "minimum_validation_group": osr.minimum_validation_group,
            "training_geometry_rows_by_class": osr.geometry_rows_by_class_,
            "training_tail_fit_rows_by_class": osr.tail_fit_rows_by_class_,
            "training_order_source": osr.training_order_source_,
            "tail_size_sensitivity_values": requested_tail_sizes,
            "tail_fit_diagnostics_file": "osr_tail_fit_diagnostics.csv",
            "tail_size_sensitivity_file": "osr_tail_size_sensitivity.csv",
            "tail_fit_diagnostic_interpretation": "descriptive in-sample diagnostics on the held-out tail-fit subset; not a formal goodness-of-fit p-value",
            "thresholds_by_nearest_class": osr.thresholds_by_class_,
            "threshold_source_by_class": osr.threshold_source_by_class_,
            "validation_known_rows": osr.validation_known_rows_,
            "validation_threshold_fit_rejection_rate": osr.validation_threshold_fit_rejection_rate_,
            "validation_threshold_fit_rejection_rate_by_nearest_class": osr.validation_threshold_fit_rejection_rate_by_nearest_class_,
            "validation_rate_is_threshold_fit_diagnostic_not_independent_test_estimate": True,
            "class_tail_parameters": {
                str(c): {"shape": t.shape, "scale": t.scale, "tail_count": t.tail_count}
                for c, t in osr.tails_.items()
            },
        },
        "conformal": {
            **conformal.theoretical_status(),
            "marginal_baseline": {
                "calibration_size": marginal.calibration_size_,
                "quantile": marginal.quantile_ if np.isfinite(marginal.quantile_) else "infinity",
            },
            "comparison_files": ["conformal_comparison.csv", "conformal_per_class_comparison.csv"],
            "operational_router_uses": "mondrian_prediction_sets",
        },
        "triage": {"minimum_evidence_margin": float(config.triage["minimum_margin"]), "policy": "singleton_set AND singleton_label_equals_classifier_top1 AND not_osr_rejected AND margin_at_least_threshold"},
        "global_metrics": global_metrics,
        "software": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "scipy": scipy.__version__,
        },
        "config_snapshot": cfg,
    }
    _write_json(run_dir / "run_metadata.json", run_metadata)
    return run_dir
