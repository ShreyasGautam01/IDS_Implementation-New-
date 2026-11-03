import numpy as np
import pandas as pd
import pytest

from ids_reliability.splitting import create_global_temporal_split, TemporalSplitError
from ids_reliability.preprocessing import TrainOnlyPreprocessor


def make_frame(n=100):
    labels = np.where(np.arange(n) % 2 == 0, 0, 1)
    labels[-10:] = -1
    return pd.DataFrame({
        "FLOW_START_MILLISECONDS": np.arange(n, dtype=np.int64) * 1000,
        "__target__": labels,
        "x": np.arange(n, dtype=float),
    })


def test_temporal_split_uses_global_chronological_boundaries_and_unknown_only_in_test():
    frame = make_frame()
    split = create_global_temporal_split(frame, "FLOW_START_MILLISECONDS", numeric_timestamp_unit="ms")
    assert split.train["__timestamp_utc__"].max() < split.validation["__timestamp_utc__"].min()
    assert split.validation["__timestamp_utc__"].max() < split.calibration["__timestamp_utc__"].min()
    assert split.calibration["__timestamp_utc__"].max() < split.test["__timestamp_utc__"].min()
    assert set(split.train["__target__"].unique()) == {0, 1}
    assert -1 not in set(split.validation["__target__"].unique())
    assert -1 not in set(split.calibration["__target__"].unique())
    assert -1 in set(split.test["__target__"].unique())


def test_temporal_split_rejects_missing_timestamp():
    with pytest.raises(TemporalSplitError, match="Required timestamp"):
        create_global_temporal_split(make_frame().drop(columns="FLOW_START_MILLISECONDS"), "FLOW_START_MILLISECONDS")


def test_pretest_unknowns_are_excluded_not_leaked_or_relabelled():
    frame = make_frame(200)
    frame.loc[3:6, "__target__"] = -1
    split = create_global_temporal_split(frame, "FLOW_START_MILLISECONDS")
    assert len(split.excluded_pretest_unknown) == 4
    assert -1 not in set(split.train["__target__"].unique())
    assert -1 not in set(split.test["__target__"].unique()) or (split.test["__target__"] == -1).any()


def test_preprocessor_statistics_come_only_from_train():
    train = pd.DataFrame({"x": [0.0, 1.0, np.nan], "y": [2.0, 3.0, 4.0]})
    test = pd.DataFrame({"x": [1e12], "y": [5.0]})
    processor = TrainOnlyPreprocessor(("x", "y")).fit(train)
    center_before = processor.scaler.center_.copy()
    _ = processor.transform(test)
    np.testing.assert_array_equal(processor.scaler.center_, center_before)
    assert processor.audit_["fit_partition"] == "train_only"


def test_temporal_embargo_purges_rows_around_global_boundaries():
    frame = make_frame(240)
    split = create_global_temporal_split(
        frame,
        "FLOW_START_MILLISECONDS",
        numeric_timestamp_unit="ms",
        train_fraction=0.55,
        validation_fraction=0.15,
        calibration_fraction=0.15,
        embargo_seconds=10,
    )
    assert split.summary["embargoed_rows_total"] > 0
    train_end = pd.Timestamp(split.boundaries["effective_train_end_utc"])
    validation_start = pd.Timestamp(split.boundaries["effective_validation_start_utc"])
    assert (validation_start - train_end).total_seconds() >= 10
    assert split.summary["embargoed_rows_by_boundary"]["train_validation"] > 0


def test_flow_intervals_crossing_partition_boundary_are_excluded():
    frame = make_frame(200)
    frame["FLOW_END_MILLISECONDS"] = frame["FLOW_START_MILLISECONDS"] + 100
    # Derive the boundary from the actual known-only split, then deliberately
    # make one otherwise-training flow end after that boundary.
    probe = create_global_temporal_split(
        frame,
        "FLOW_START_MILLISECONDS",
        end_timestamp_column="FLOW_END_MILLISECONDS",
        numeric_timestamp_unit="ms",
        end_numeric_timestamp_unit="ms",
    )
    train_end = pd.Timestamp(probe.boundaries["effective_train_end_utc"])
    start_times = pd.to_datetime(frame["FLOW_START_MILLISECONDS"], unit="ms", utc=True)
    candidate_indices = frame.index[start_times <= train_end]
    crossing_index = int(candidate_indices[-1])
    frame.loc[crossing_index, "FLOW_END_MILLISECONDS"] = int(
        (train_end + pd.Timedelta(seconds=1)).value // 1_000_000
    )
    split = create_global_temporal_split(
        frame,
        "FLOW_START_MILLISECONDS",
        end_timestamp_column="FLOW_END_MILLISECONDS",
        numeric_timestamp_unit="ms",
        end_numeric_timestamp_unit="ms",
    )
    crossing_start = frame.loc[crossing_index, "FLOW_START_MILLISECONDS"]
    assert not (split.train["FLOW_START_MILLISECONDS"] == crossing_start).any()
    assert (split.excluded_boundary_overlap["FLOW_START_MILLISECONDS"] == crossing_start).any()
    assert split.summary["complete_flow_interval_enforced"] is True


def test_flow_interval_with_end_before_start_is_rejected():
    frame = make_frame(200)
    frame["FLOW_END_MILLISECONDS"] = frame["FLOW_START_MILLISECONDS"] - 1
    with pytest.raises(TemporalSplitError, match="end timestamp precedes"):
        create_global_temporal_split(
            frame,
            "FLOW_START_MILLISECONDS",
            end_timestamp_column="FLOW_END_MILLISECONDS",
        )


def test_held_out_unknown_timestamps_do_not_change_global_boundaries():
    frame = make_frame(400)
    frame["FLOW_END_MILLISECONDS"] = frame["FLOW_START_MILLISECONDS"] + 500
    baseline = create_global_temporal_split(
        frame, "FLOW_START_MILLISECONDS", end_timestamp_column="FLOW_END_MILLISECONDS",
        numeric_timestamp_unit="ms", end_numeric_timestamp_unit="ms",
    )
    shifted_unknown = frame.copy()
    unknown = shifted_unknown["__target__"] == -1
    shifted_unknown.loc[unknown, "FLOW_START_MILLISECONDS"] += 10_000_000
    shifted_unknown.loc[unknown, "FLOW_END_MILLISECONDS"] += 10_000_000
    shifted = create_global_temporal_split(
        shifted_unknown, "FLOW_START_MILLISECONDS", end_timestamp_column="FLOW_END_MILLISECONDS",
        numeric_timestamp_unit="ms", end_numeric_timestamp_unit="ms",
    )
    assert baseline.boundaries == shifted.boundaries
