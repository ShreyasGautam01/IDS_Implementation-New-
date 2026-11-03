from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import numpy as np
import pandas as pd


class TemporalSplitError(ValueError):
    pass


@dataclass(frozen=True)
class TemporalSplit:
    train: pd.DataFrame
    validation: pd.DataFrame
    calibration: pd.DataFrame
    test: pd.DataFrame
    excluded_pretest_unknown: pd.DataFrame
    excluded_boundary_overlap: pd.DataFrame
    boundaries: dict[str, str]
    summary: dict[str, Any]


def parse_timestamp(series: pd.Series, numeric_unit: str = "ms") -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        result = pd.to_datetime(series, unit=numeric_unit, utc=True, errors="coerce")
    else:
        result = pd.to_datetime(series, utc=True, errors="coerce")
    invalid = int(result.isna().sum())
    if invalid:
        raise TemporalSplitError(
            f"Timestamp column has {invalid} missing or unparseable values"
        )
    return result


def _global_boundaries(
    times: pd.Series, fractions: tuple[float, float, float]
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    counts = times.value_counts(sort=False).sort_index()
    if len(counts) < 4:
        raise TemporalSplitError(
            "At least four distinct timestamps are required for four non-empty temporal periods"
        )
    cumulative = counts.cumsum().to_numpy()
    total = int(cumulative[-1])
    boundaries: list[pd.Timestamp] = []
    previous_index = -1
    for fraction in fractions:
        target = fraction * total
        index = int(np.searchsorted(cumulative, target, side="left"))
        if index <= previous_index:
            index = previous_index + 1
        if index >= len(counts) - 1:
            raise TemporalSplitError(
                "Temporal split fractions leave no observations for a later partition"
            )
        boundaries.append(pd.Timestamp(counts.index[index]))
        previous_index = index
    if not boundaries[0] < boundaries[1] < boundaries[2]:
        raise TemporalSplitError("Could not create strictly increasing global time boundaries")
    return boundaries[0], boundaries[1], boundaries[2]


def create_global_temporal_split(
    frame: pd.DataFrame,
    timestamp_column: str,
    target_column: str = "__target__",
    numeric_timestamp_unit: str = "ms",
    end_timestamp_column: str | None = None,
    end_numeric_timestamp_unit: str | None = None,
    train_fraction: float = 0.55,
    validation_fraction: float = 0.15,
    calibration_fraction: float = 0.15,
    embargo_seconds: float = 0.0,
    require_unknown_in_test: bool = True,
) -> TemporalSplit:
    """Create four global, forward-in-time partitions.

    Equal start timestamps remain in the same time partition. When an end-time
    column is configured, each retained flow must lie wholly within its assigned
    period. Flows crossing an effective partition boundary are explicitly
    excluded, preventing a flow that starts in one period and ends in another
    from straddling the train/validation/calibration/test boundary.

    ``embargo_seconds`` is the total purged interval width around each nominal
    boundary. This prevents near-boundary flow overlap but does not prove that
    longer attack campaigns or duplicate sessions cannot span periods.
    """
    if timestamp_column not in frame:
        raise TemporalSplitError(
            f"Required timestamp column {timestamp_column!r} is absent. "
            "A chronological evaluation cannot be claimed without a verified temporal key."
        )
    if target_column not in frame:
        raise TemporalSplitError(f"Target column {target_column!r} is absent")
    if end_timestamp_column is not None and end_timestamp_column not in frame:
        raise TemporalSplitError(
            f"Configured flow end-time column {end_timestamp_column!r} is absent. "
            "Disable it only if the dataset genuinely does not provide flow end times."
        )

    test_fraction = 1.0 - train_fraction - validation_fraction - calibration_fraction
    if min(train_fraction, validation_fraction, calibration_fraction, test_fraction) <= 0:
        raise TemporalSplitError("All four temporal fractions must be strictly positive")
    if embargo_seconds < 0:
        raise TemporalSplitError("embargo_seconds cannot be negative")
    if not np.isclose(
        train_fraction + validation_fraction + calibration_fraction + test_fraction,
        1.0,
    ):
        raise TemporalSplitError("Temporal fractions must sum to one")

    work = frame.copy().reset_index(drop=True)
    start_time = parse_timestamp(work[timestamp_column], numeric_timestamp_unit)
    work["__timestamp_utc__"] = start_time
    if end_timestamp_column is not None:
        end_unit = end_numeric_timestamp_unit or numeric_timestamp_unit
        end_time = parse_timestamp(work[end_timestamp_column], end_unit)
        invalid_interval = end_time < start_time
        if invalid_interval.any():
            raise TemporalSplitError(
                f"Found {int(invalid_interval.sum())} flows whose end timestamp precedes their start timestamp"
            )
        work["__flow_end_utc__"] = end_time
    else:
        # Explicitly mark this weaker mode in metadata; do not imply complete-flow
        # interval separation when only the start time is known.
        work["__flow_end_utc__"] = start_time

    # Partition boundaries are derived from known-family records only. The
    # withheld family must not influence the temporal cut points through its
    # event-time distribution; its observations are evaluated only if they fall
    # after the known-data-derived test boundary.
    known_for_boundary = work.loc[work[target_column].astype(int) >= 0, "__timestamp_utc__"]
    if known_for_boundary.empty:
        raise TemporalSplitError("No known-class rows are available to determine temporal boundaries")
    b1, b2, b3 = _global_boundaries(
        known_for_boundary,
        (
            train_fraction,
            train_fraction + validation_fraction,
            train_fraction + validation_fraction + calibration_fraction,
        ),
    )
    is_unknown = work[target_column].astype(int) == -1
    start = work["__timestamp_utc__"]
    end = work["__flow_end_utc__"]
    half_gap = pd.Timedelta(seconds=float(embargo_seconds) / 2.0)
    train_end = b1 - half_gap
    validation_start = b1 + half_gap
    validation_end = b2 - half_gap
    calibration_start = b2 + half_gap
    calibration_end = b3 - half_gap
    test_start = b3 + half_gap

    # Start-time membership in the explicit embargo windows.
    gap_1 = (start > train_end) & (start <= validation_start)
    gap_2 = (start > validation_end) & (start <= calibration_start)
    gap_3 = (start > calibration_end) & (start <= test_start)
    start_in_embargo = gap_1 | gap_2 | gap_3

    # Exclude a flow if its interval crosses an effective end boundary. The
    # test period is open-ended, so only the first three end boundaries matter.
    crosses_train_end = (start <= train_end) & (end > train_end)
    crosses_validation_end = (start <= validation_end) & (end > validation_end)
    crosses_calibration_end = (start <= calibration_end) & (end > calibration_end)
    crosses_boundary = crosses_train_end | crosses_validation_end | crosses_calibration_end
    boundary_overlap = start_in_embargo | crosses_boundary

    train_mask = (start <= train_end) & (end <= train_end) & ~is_unknown
    validation_mask = (
        (start > validation_start)
        & (end <= validation_end)
        & ~is_unknown
    )
    calibration_mask = (
        (start > calibration_start)
        & (end <= calibration_end)
        & ~is_unknown
    )
    test_mask = start > test_start
    excluded_unknown_mask = is_unknown & ~test_mask
    assigned = train_mask | validation_mask | calibration_mask | test_mask
    excluded_boundary_mask = ~assigned & ~excluded_unknown_mask

    parts = {
        "train": work.loc[train_mask].copy(),
        "validation": work.loc[validation_mask].copy(),
        "calibration": work.loc[calibration_mask].copy(),
        "test": work.loc[test_mask].copy(),
        "excluded_pretest_unknown": work.loc[excluded_unknown_mask].copy(),
        "excluded_boundary_overlap": work.loc[excluded_boundary_mask].copy(),
    }
    for name in ("train", "validation", "calibration", "test"):
        if parts[name].empty:
            raise TemporalSplitError(f"Temporal partition {name!r} is empty")
    if any(
        (parts[name][target_column].astype(int) == -1).any()
        for name in ("train", "validation", "calibration")
    ):
        raise AssertionError("Held-out unknown samples leaked into a pre-test partition")

    train_classes = set(parts["train"][target_column].astype(int).unique())
    later_known = (
        set(
            pd.concat([parts["validation"], parts["calibration"], parts["test"]])[
                target_column
            ].astype(int).unique()
        )
        - {-1}
    )
    missing_training = sorted(later_known - train_classes)
    if missing_training:
        raise TemporalSplitError(
            "Some known classes first occur after the training window and cannot be learned "
            f"under this temporal protocol: {missing_training}. Do not silently relabel them; "
            "revise the training window or report them as unseen classes in a separate protocol."
        )
    if require_unknown_in_test and not (parts["test"][target_column].astype(int) == -1).any():
        raise TemporalSplitError(
            "No held-out-family observations occur in the locked test time window"
        )

    unexpected_unassigned = ~assigned & ~excluded_unknown_mask & ~boundary_overlap
    if unexpected_unassigned.any():
        raise AssertionError(
            f"Found {int(unexpected_unassigned.sum())} known rows outside primary partitions "
            "that are not explained by the configured embargo or flow-boundary overlap"
        )

    def part_summary(part: pd.DataFrame) -> dict[str, Any]:
        if part.empty:
            return {"rows": 0, "class_counts": {}, "start_min_utc": None,
                    "start_max_utc": None, "flow_end_max_utc": None}
        return {
            "rows": int(len(part)),
            "class_counts": {
                str(k): int(v)
                for k, v in part[target_column].value_counts().sort_index().items()
            },
            "start_min_utc": part["__timestamp_utc__"].min().isoformat(),
            "start_max_utc": part["__timestamp_utc__"].max().isoformat(),
            "flow_end_max_utc": part["__flow_end_utc__"].max().isoformat(),
        }

    summary = {name: part_summary(part) for name, part in parts.items()}
    summary.update(
        {
            "unknown_test_rows": int(
                (parts["test"][target_column].astype(int) == -1).sum()
            ),
            "unknown_excluded_before_test": int(len(parts["excluded_pretest_unknown"])),
            "boundary_overlap_excluded_rows": int(len(parts["excluded_boundary_overlap"])),
            "embargoed_rows_total": int(len(parts["excluded_boundary_overlap"])),
            "boundary_overlap_rows_detected": int(boundary_overlap.sum()),
            "embargo_start_rows_by_boundary": {
                "train_validation": int(gap_1.sum()),
                "validation_calibration": int(gap_2.sum()),
                "calibration_test": int(gap_3.sum()),
            },
            "embargoed_rows_by_boundary": {
                "train_validation": int(gap_1.sum()),
                "validation_calibration": int(gap_2.sum()),
                "calibration_test": int(gap_3.sum()),
            },
            "crossing_flow_rows_by_boundary": {
                "train_validation": int(crosses_train_end.sum()),
                "validation_calibration": int(crosses_validation_end.sum()),
                "calibration_test": int(crosses_calibration_end.sum()),
            },
            "embargo_seconds_total_per_boundary": float(embargo_seconds),
            "complete_flow_interval_enforced": end_timestamp_column is not None,
            "start_timestamp_column": timestamp_column,
            "end_timestamp_column": end_timestamp_column,
            "time_ordering": "global_start_end_boundaries_with_embargo"
            if end_timestamp_column is not None
            else "global_start_timestamp_boundaries_only",
            "partition_audit_note": (
                "Excluded audit subsets may overlap conceptually with unknown-family exclusions; "
                "the four primary partitions are mutually exclusive."
            ),
        }
    )

    return TemporalSplit(
        train=parts["train"],
        validation=parts["validation"],
        calibration=parts["calibration"],
        test=parts["test"],
        excluded_pretest_unknown=parts["excluded_pretest_unknown"],
        excluded_boundary_overlap=parts["excluded_boundary_overlap"],
        boundaries={
            "nominal_train_boundary_utc": b1.isoformat(),
            "nominal_validation_boundary_utc": b2.isoformat(),
            "nominal_calibration_boundary_utc": b3.isoformat(),
            "effective_train_end_utc": train_end.isoformat(),
            "effective_validation_start_utc": validation_start.isoformat(),
            "effective_validation_end_utc": validation_end.isoformat(),
            "effective_calibration_start_utc": calibration_start.isoformat(),
            "effective_calibration_end_utc": calibration_end.isoformat(),
            "effective_test_start_exclusive_utc": test_start.isoformat(),
            "embargo_seconds_total_per_boundary": float(embargo_seconds),
        },
        summary=summary,
    )
