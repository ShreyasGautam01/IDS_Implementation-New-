from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import math
import yaml


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    raw: dict[str, Any]
    source_path: Path

    @property
    def dataset(self) -> dict[str, Any]:
        return self.raw["dataset"]

    @property
    def split(self) -> dict[str, Any]:
        return self.raw["split"]

    @property
    def features(self) -> dict[str, Any]:
        return self.raw["features"]

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    @property
    def osr(self) -> dict[str, Any]:
        return self.raw["osr"]

    @property
    def conformal(self) -> dict[str, Any]:
        return self.raw["conformal"]

    @property
    def triage(self) -> dict[str, Any]:
        return self.raw["triage"]

    @property
    def output(self) -> dict[str, Any]:
        return self.raw["output"]


def _require_mapping(section: Any, name: str) -> dict[str, Any]:
    if not isinstance(section, dict):
        raise ConfigurationError(f"Configuration section {name!r} must be a mapping")
    return section


def load_config(path: str | Path) -> AppConfig:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ConfigurationError(f"Configuration file does not exist: {source}")
    try:
        with source.open("r", encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {source}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("Configuration root must be a mapping")

    required = {
        "dataset", "split", "features", "model", "osr", "conformal", "triage", "output"
    }
    missing = required.difference(raw)
    if missing:
        raise ConfigurationError(f"Missing top-level configuration sections: {sorted(missing)}")
    for section in required:
        _require_mapping(raw[section], section)

    dataset = raw["dataset"]
    for key in ("path", "label_column", "timestamp_column", "unknown_family"):
        if key not in dataset or not str(dataset[key]).strip():
            raise ConfigurationError(f"dataset.{key} must be a non-empty value")
    if dataset.get("end_timestamp_column") and (
        str(dataset["end_timestamp_column"]) == str(dataset["timestamp_column"])
    ):
        raise ConfigurationError("dataset.end_timestamp_column must differ from timestamp_column")
    supported_time_units = {"s", "ms", "us", "ns"}
    start_unit = str(dataset.get("numeric_timestamp_unit", "ms"))
    end_unit = str(dataset.get("end_numeric_timestamp_unit", start_unit))
    if start_unit not in supported_time_units:
        raise ConfigurationError(
            "dataset.numeric_timestamp_unit must be one of s, ms, us, or ns"
        )
    if end_unit not in supported_time_units:
        raise ConfigurationError(
            "dataset.end_numeric_timestamp_unit must be one of s, ms, us, or ns"
        )

    split = raw["split"]
    fraction_keys = ("train_fraction", "validation_fraction", "calibration_fraction")
    try:
        fractions = [float(split[key]) for key in fraction_keys]
        embargo_seconds = float(split.get("embargo_seconds", 0.0))
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid split fraction or embargo value: {exc}") from exc
    if any(not math.isfinite(value) or value <= 0 for value in fractions) or sum(fractions) >= 1:
        raise ConfigurationError(
            "Train, validation, and calibration fractions must all be positive and sum to less than one"
        )
    if not math.isfinite(embargo_seconds) or embargo_seconds < 0:
        raise ConfigurationError("split.embargo_seconds cannot be negative")

    features = raw["features"]
    if str(features.get("schema_level", "")).casefold() not in {
        "baseline", "set_a", "set_b", "set_c"
    }:
        raise ConfigurationError("features.schema_level must be baseline, set_a, set_b, or set_c")
    if not isinstance(features.get("groups"), dict) or not isinstance(features.get("identifiers"), list):
        raise ConfigurationError("features.groups must be a mapping and features.identifiers a list")

    model = raw["model"]
    parameters = model.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ConfigurationError("model.parameters must be a mapping")

    osr = raw["osr"]
    try:
        tail_size = int(osr["tail_size"])
        target_known_fpr = float(osr["target_known_fpr"])
        geometry_fraction = float(osr.get("geometry_fraction", 0.70))
        minimum_validation_group = int(osr.get("minimum_validation_group", 20))
        sensitivity = [int(value) for value in osr.get("tail_size_sensitivity", [tail_size])]
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid OSR parameter: {exc}") from exc
    if tail_size < 5 or not sensitivity or any(value < 5 for value in sensitivity):
        raise ConfigurationError("OSR tail sizes must be at least five")
    if not math.isfinite(target_known_fpr) or not 0 < target_known_fpr < 1:
        raise ConfigurationError("osr.target_known_fpr must be between 0 and 1")
    if not math.isfinite(geometry_fraction) or not 0.5 <= geometry_fraction < 1:
        raise ConfigurationError("osr.geometry_fraction must be in [0.5, 1)")
    if minimum_validation_group < 2:
        raise ConfigurationError("osr.minimum_validation_group must be at least two")

    alpha = float(raw["conformal"].get("alpha", 0.0))
    if not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ConfigurationError("conformal.alpha must be between 0 and 1")
    margin = float(raw["triage"].get("minimum_margin", -1.0))
    if not math.isfinite(margin) or not 0 <= margin <= 1:
        raise ConfigurationError("triage.minimum_margin must be in [0, 1]")
    if not str(raw["output"].get("directory", "")).strip():
        raise ConfigurationError("output.directory must be a non-empty path")

    evaluation = raw.get("evaluation", {})
    if not isinstance(evaluation, dict):
        raise ConfigurationError("evaluation must be a mapping")
    minimum_unknown_test_rows = int(evaluation.get("minimum_unknown_test_rows", 20))
    if minimum_unknown_test_rows < 2:
        raise ConfigurationError("evaluation.minimum_unknown_test_rows must be at least two")

    monotonicity = raw.get("monotonicity", {})
    if monotonicity:
        fraction = float(monotonicity.get("benign_augmentation_fraction", 0.05))
        shift = float(monotonicity.get("benign_augmentation_iqr", 6.0))
        epsilons = [float(value) for value in monotonicity.get("epsilon_values", [0.0, 0.25, 0.5, 0.75, 1.0])]
        if not 0 <= fraction <= 1 or shift < 0:
            raise ConfigurationError("monotonicity augmentation fraction must be in [0,1] and IQR shift nonnegative")
        if not epsilons or epsilons[0] < 0 or any(right <= left for left, right in zip(epsilons, epsilons[1:])):
            raise ConfigurationError("monotonicity.epsilon_values must be strictly increasing and nonnegative")

    return AppConfig(raw=raw, source_path=source)
