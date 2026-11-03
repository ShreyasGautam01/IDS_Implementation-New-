import numpy as np
import pandas as pd
import pytest

from ids_reliability.labels import build_label_mapping
from ids_reliability.features import select_features, FeatureSchemaError


def test_label_mapping_is_deterministic_and_withholds_unknown():
    mapping = build_label_mapping(["Benign", "DoS", "Fuzzers", "Worms"], "Worms")
    assert mapping.label_to_id["Benign"] == 0
    assert mapping.label_to_id["Worms"] == -1
    assert mapping.encode(["Worms", "Benign", "Fuzzers"]) == [-1, 0, mapping.label_to_id["Fuzzers"]]


def test_label_mapping_rejects_absent_unknown_family():
    with pytest.raises(ValueError, match="must occur"):
        build_label_mapping(["Benign", "DoS"], "Worms")


def _frame():
    return pd.DataFrame({
        "FLOW_START_MILLISECONDS": [1, 2],
        "IPV4_SRC_ADDR": ["a", "b"],
        "MIN_TTL": [64, 63],
        "TCP_WIN_MAX_IN": [10, 11],
        "PROTOCOL": [6, 17],
        "BYTES": [100, 200],
        "PKTS": [2, 3],
        "Attack": ["Benign", "DoS"],
        "Label": [0, 1],
    })


def test_feature_ablation_is_explicit_and_progressive():
    frame = _frame()
    groups = {"ttl": ["MIN_TTL"], "window": ["TCP_WIN_MAX_IN"], "protocol": ["PROTOCOL"]}
    identifiers = ["IPV4_SRC_ADDR"]
    baseline = select_features(frame, ["Attack", "Label"], "FLOW_START_MILLISECONDS", "baseline", groups, identifiers)
    set_c = select_features(frame, ["Attack", "Label"], "FLOW_START_MILLISECONDS", "set_c", groups, identifiers)
    assert baseline.columns == ("MIN_TTL", "TCP_WIN_MAX_IN", "PROTOCOL", "BYTES", "PKTS")
    assert set_c.columns == ("BYTES", "PKTS")
    assert set_c.removed_by_group["ttl"] == ("MIN_TTL",)


def test_unexpected_nonnumeric_predictor_is_not_silently_dropped():
    frame = _frame()
    frame["unrecognised_text"] = ["x", "y"]
    with pytest.raises(FeatureSchemaError, match="not silently dropping"):
        select_features(frame, ["Attack", "Label"], "FLOW_START_MILLISECONDS", "set_c",
                        {"ttl": [], "window": [], "protocol": []}, ["IPV4_SRC_ADDR"])
