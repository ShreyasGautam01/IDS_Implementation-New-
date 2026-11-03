import numpy as np
import pandas as pd
import yaml

from ids_reliability.config import AppConfig
from ids_reliability.pipeline import run_pipeline


def test_complete_pipeline_runs_on_synthetic_time_ordered_csv(tmp_path):
    rng = np.random.default_rng(18)
    rows = []
    labels = ["Benign", "DoS", "Fuzzers"]
    for i in range(1200):
        if i >= 1020 and i % 3 == 0:
            label = "Worms"
        else:
            label = labels[i % len(labels)]
        center = {"Benign": 0.0, "DoS": 3.0, "Fuzzers": 6.0, "Worms": 12.0}[label]
        rows.append({
            "FLOW_START_MILLISECONDS": 1_700_000_000_000 + i * 1000,
            "FLOW_END_MILLISECONDS": 1_700_000_000_500 + i * 1000,
            "Attack": label,
            "Label": 0 if label == "Benign" else 1,
            "BYTES": max(1.0, rng.normal(center + 10, 1)),
            "PKTS": max(1.0, rng.normal(center + 5, 1)),
            "THROUGHPUT": max(1.0, rng.normal(center + 2, 0.5)),
            "IN_PKTS": 2.0,
            "OUT_PKTS": 3.0,
            "DURATION": 10.0,
            "MIN_TTL": 64.0,
            "MAX_TTL": 64.0,
            "TCP_WIN_MAX_IN": 100.0,
            "PROTOCOL": 6.0,
        })
    dataset = tmp_path / "synthetic.csv"
    pd.DataFrame(rows).to_csv(dataset, index=False)
    cfg = {
        "dataset": {
            "path": str(dataset), "label_column": "Attack", "binary_label_column": "Label",
            "timestamp_column": "FLOW_START_MILLISECONDS", "end_timestamp_column": "FLOW_END_MILLISECONDS", "numeric_timestamp_unit": "ms",
            "unknown_family": "Worms", "benign_aliases": ["Benign", "Normal", "BENIGN", "0"],
            "packet_columns": ["IN_PKTS", "OUT_PKTS"], "duplicate_audit_sample_size": 2000,
            "compute_sha256": False,
        },
        "split": {"train_fraction": 0.55, "validation_fraction": 0.15, "calibration_fraction": 0.15},
        "features": {
            "schema_level": "set_c", "clip_limit": 1e15,
            "identifiers": ["FLOW_START_MILLISECONDS"],
            "groups": {"ttl": ["MIN_TTL", "MAX_TTL"], "window": ["TCP_WIN_MAX_IN"], "protocol": ["PROTOCOL"]},
        },
        "model": {"random_state": 42, "parameters": {"max_iter": 30, "max_leaf_nodes": 15, "min_samples_leaf": 5, "class_weight": "balanced"}},
        "osr": {"tail_size": 20, "tail_size_sensitivity": [10, 20], "geometry_fraction": 0.70, "target_known_fpr": 0.05},
        "conformal": {"alpha": 0.10},
        "triage": {"minimum_margin": 0.25},
        "evaluation": {"minimum_unknown_test_rows": 20},
        "output": {"directory": str(tmp_path / "out")},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    config = AppConfig(raw=cfg, source_path=config_path)
    run_dir = run_pipeline(config)
    assert (run_dir / "test_predictions.csv").is_file()
    assert (run_dir / "per_class_metrics.csv").is_file()
    assert (run_dir / "run_metadata.json").is_file()
    assert (run_dir / "conformal_comparison.csv").is_file()
    assert (run_dir / "conformal_per_class_comparison.csv").is_file()
    assert (run_dir / "osr_tail_fit_diagnostics.csv").is_file()
    assert (run_dir / "osr_tail_size_sensitivity.csv").is_file()
    import json
    run_metadata = json.loads((run_dir / "run_metadata.json").read_text())
    assert "singleton_label_equals_classifier_top1" in run_metadata["triage"]["policy"]
    cp_comparison = pd.read_csv(run_dir / "conformal_comparison.csv")
    assert set(cp_comparison["method"]) == {"marginal", "mondrian"}
    metrics = pd.read_csv(run_dir / "per_class_metrics.csv")
    assert "Unknown_held_out" in set(metrics["class"])
