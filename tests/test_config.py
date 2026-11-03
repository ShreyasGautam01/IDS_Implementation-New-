from pathlib import Path
import pytest
import yaml

from ids_reliability.config import load_config, ConfigurationError


def test_default_config_is_loadable():
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "configs" / "default.yaml")
    assert config.conformal["alpha"] == 0.10


def test_invalid_alpha_is_rejected(tmp_path):
    raw = {
        "dataset": {
            "path": "dataset.csv", "label_column": "Attack",
            "timestamp_column": "FLOW_START_MILLISECONDS", "unknown_family": "Worms",
        },
        "split": {"train_fraction": 0.5, "validation_fraction": 0.2, "calibration_fraction": 0.2},
        "features": {"schema_level": "set_c", "groups": {}, "identifiers": []},
        "model": {"parameters": {}},
        "osr": {"tail_size": 50, "target_known_fpr": 0.05},
        "conformal": {"alpha": 1.0},
        "triage": {"minimum_margin": 0.2},
        "output": {"directory": "artifacts"},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ConfigurationError, match="alpha"):
        load_config(path)


@pytest.mark.parametrize("bad_unit", ["minute", "", "MS"])
def test_unsupported_numeric_timestamp_unit_is_rejected(tmp_path, bad_unit):
    raw = {
        "dataset": {
            "path": "dataset.csv", "label_column": "Attack",
            "timestamp_column": "FLOW_START_MILLISECONDS", "unknown_family": "Worms",
            "numeric_timestamp_unit": bad_unit,
        },
        "split": {"train_fraction": 0.5, "validation_fraction": 0.2, "calibration_fraction": 0.2},
        "features": {"schema_level": "set_c", "groups": {}, "identifiers": []},
        "model": {"parameters": {}},
        "osr": {"tail_size": 50, "target_known_fpr": 0.05},
        "conformal": {"alpha": 0.1},
        "triage": {"minimum_margin": 0.2},
        "output": {"directory": "artifacts"},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ConfigurationError, match="numeric_timestamp_unit"):
        load_config(path)


def test_nan_split_fraction_is_rejected(tmp_path):
    root = Path(__file__).resolve().parents[1]
    raw = yaml.safe_load((root / "configs" / "default.yaml").read_text())
    raw["split"]["train_fraction"] = float("nan")
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ConfigurationError, match="fractions"):
        load_config(path)
