import numpy as np
import pandas as pd

from ids_reliability.config import AppConfig
from ids_reliability.transfer import run_cross_dataset_experiment, _load_binary_disjoint_samples
from ids_reliability.monotonic import run_binary_monotonicity_experiment


def _binary_frame(n, offset=0):
    rng = np.random.default_rng(71 + offset)
    y = np.arange(n) % 2
    base = y * 4.0
    return pd.DataFrame({
        "FLOW_START_MILLISECONDS": 1_700_000_000_000 + np.arange(n) * 1000,
        "FLOW_END_MILLISECONDS": 1_700_000_000_000 + np.arange(n) * 1000 + 500,
        "Label": y,
        "Attack": np.where(y == 0, "Benign", "Attack"),
        "BYTES": np.maximum(1, 10 + base + rng.normal(0, 1, n)),
        "PKTS": np.maximum(1, 4 + base + rng.normal(0, 1, n)),
        "IN_PKTS": 2.0,
        "OUT_PKTS": 3.0,
        "DURATION": 2.0,
    })


def _config(tmp_path, max_iter=10):
    raw = {
        "dataset": {
            "path": str(tmp_path / "dataset_a.csv"), "label_column": "Attack", "binary_label_column": "Label",
            "timestamp_column": "FLOW_START_MILLISECONDS", "end_timestamp_column": "FLOW_END_MILLISECONDS", "numeric_timestamp_unit": "ms", "end_numeric_timestamp_unit": "ms", "unknown_family": "Attack",
            "benign_aliases": ["Benign"], "packet_columns": ["IN_PKTS", "OUT_PKTS"],
            "transfer_source_sample_size": 160, "transfer_sample_seed_dataset_a": 31,
            "transfer_target_sample_size": 100, "transfer_sample_seed_dataset_b": 32,
            "transfer_chunk_rows": 73,
        },
        "split": {"train_fraction": 0.55, "validation_fraction": 0.15, "calibration_fraction": 0.15},
        "features": {
            "schema_level": "set_c", "clip_limit": 1e15, "identifiers": ["FLOW_START_MILLISECONDS", "FLOW_END_MILLISECONDS"],
            "groups": {"ttl": ["MIN_TTL"], "window": ["TCP_WIN_MAX_IN"], "protocol": ["PROTOCOL"]},
            "monotonic_volume_keywords": ["BYTES", "PKTS"],
        },
        "model": {"random_state": 4, "transfer_seeds": [4], "parameters": {"max_iter": max_iter, "max_leaf_nodes": 7, "min_samples_leaf": 4}},
        "osr": {"tail_size": 10, "target_known_fpr": 0.05},
        "conformal": {"alpha": 0.1},
        "triage": {"minimum_margin": 0.2},
        "evaluation": {"minimum_unknown_test_rows": 20},
        "output": {"directory": str(tmp_path / "output")},
        "monotonicity": {"benign_augmentation_fraction": 0.05, "benign_augmentation_iqr": 6.0, "epsilon_values": [0.0, 0.5, 1.0]},
    }
    return AppConfig(raw=raw, source_path=tmp_path / "unused.yaml")


def test_cross_dataset_experiment_uses_fixed_target_sample_and_writes_summary(tmp_path):
    a = _binary_frame(300, 0)
    b = _binary_frame(320, 1)
    a_path, b_path = tmp_path / "dataset_a.csv", tmp_path / "dataset_b.csv"
    a.to_csv(a_path, index=False)
    b.to_csv(b_path, index=False)
    config = _config(tmp_path)
    result_dir = run_cross_dataset_experiment(config, a_path, b_path, seeds=[4])
    detail = pd.read_csv(result_dir / "cross_dataset_per_seed.csv")
    summary = pd.read_csv(result_dir / "cross_dataset_summary.csv")
    assert len(detail) == 8  # four schemas × two directions × one seed
    assert not summary.empty
    assert set(detail["target_evaluation_rows"]) == {100}
    assert all(int(v) <= 90 for v in detail["source_train_rows"])


def test_cross_dataset_transfer_supports_v2_data_without_timestamps(tmp_path):
    a = _binary_frame(300, 0).drop(columns=["FLOW_START_MILLISECONDS", "FLOW_END_MILLISECONDS"])
    b = _binary_frame(320, 1).drop(columns=["FLOW_START_MILLISECONDS", "FLOW_END_MILLISECONDS"])
    a_path, b_path = tmp_path / "dataset_a.csv", tmp_path / "dataset_b.csv"
    a.to_csv(a_path, index=False)
    b.to_csv(b_path, index=False)
    config = _config(tmp_path)
    result_dir = run_cross_dataset_experiment(config, a_path, b_path, seeds=[4])
    detail = pd.read_csv(result_dir / "cross_dataset_per_seed.csv")
    assert set(detail["source_split_strategy"]) == {"stratified_random_no_timestamp_available"}
    assert detail["source_split_strategy"].notna().all()


def test_binary_monotonicity_experiment_is_separate_and_emits_audit(tmp_path):
    data = _binary_frame(600)
    path = tmp_path / "binary.csv"
    data.to_csv(path, index=False)
    config = _config(tmp_path, max_iter=20)
    output = run_binary_monotonicity_experiment(config, path, seed=4)
    result = pd.read_csv(output / "binary_monotonicity_sensitivity.csv")
    assert set(result["model"]) == {"unconstrained", "monotone_binary"}
    assert len(result) == 6
    import json
    metadata = json.loads((output / "experiment_metadata.json").read_text())
    assert metadata["monotonicity_audit"]["negative_probability_steps_below_tolerance"] == 0
    assert (output / "monotonicity_feature_audit.csv").is_file()
    assert "Binary sensitivity experiment only" in metadata["scope_warning"]


def test_chunked_transfer_sampler_returns_disjoint_uniform_role_samples(tmp_path):
    frame = _binary_frame(360)
    frame["row_id"] = np.arange(len(frame))
    path = tmp_path / "streamed.csv"
    frame.to_csv(path, index=False)
    source, target, audit = _load_binary_disjoint_samples(
        path, "Label", source_sample_size=120, target_sample_size=100,
        seed=73, chunk_rows=41,
    )
    assert len(source) == 120
    assert len(target) == 100
    assert set(source["__target__"].unique()) == {0, 1}
    assert set(target["__target__"].unique()) == {0, 1}
    assert set(source["row_id"]).isdisjoint(set(target["row_id"]))
    assert audit["chunk_count"] > 1
    assert audit["samples_disjoint"] is True
    source_repeat, target_repeat, _ = _load_binary_disjoint_samples(
        path, "Label", source_sample_size=120, target_sample_size=100,
        seed=73, chunk_rows=41,
    )
    assert source["row_id"].tolist() == source_repeat["row_id"].tolist()
    assert target["row_id"].tolist() == target_repeat["row_id"].tolist()
