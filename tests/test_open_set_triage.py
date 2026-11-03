import numpy as np
import pandas as pd
import pytest

from ids_reliability.open_set import OpenSetError

from ids_reliability.open_set import MahalanobisWeibullDetector
from ids_reliability.triage import evaluate_triage


def test_open_set_detector_fits_and_calibrates_separate_validation_threshold():
    rng = np.random.default_rng(4)
    x0 = rng.normal(0, 0.5, (120, 3))
    x1 = rng.normal(4, 0.5, (120, 3))
    x_train = np.vstack([x0, x1])
    y_train = np.array([0] * len(x0) + [1] * len(x1))
    y_pred = y_train.copy()
    timestamps = pd.date_range("2020-01-01", periods=len(y_train), freq="s", tz="UTC")
    detector = MahalanobisWeibullDetector(tail_size=20, target_known_fpr=0.05).fit(x_train, y_train, timestamps=timestamps)
    x_val = np.vstack([rng.normal(0, 0.5, (30, 3)), rng.normal(4, 0.5, (30, 3))])
    y_val = np.array([0] * 30 + [1] * 30)
    detector.calibrate_threshold(x_val, y_val)
    x_test = np.vstack([rng.normal(0, 0.5, (10, 3)), rng.normal(8, 0.5, (10, 3))])
    scores, rejected = detector.reject(x_test)
    assert len(scores) == 20
    assert rejected[-10:].mean() > rejected[:10].mean()
    assert detector.thresholds_by_class_
    diagnostics = detector.tail_fit_diagnostics()
    assert set(diagnostics["geometry_rows"]) == {84}
    assert set(diagnostics["tail_fit_rows"]) == {36}
    variant = detector.with_tail_size(10)
    assert variant.tail_size == 10
    assert variant.classes_.tolist() == detector.classes_.tolist()


def test_triage_reports_unknown_osr_and_escalation_separately():
    probabilities = np.array([[0.9, 0.1], [0.8, 0.2], [0.2, 0.8], [0.7, 0.3]])
    sets = np.array([[1, 0], [1, 0], [0, 1], [1, 0]], dtype=bool)
    margin = np.array([0.8, 0.1, 0.7, 0.8])
    osr_scores = np.array([0.1, 0.2, 0.1, 0.9])
    osr_rejected = np.array([False, False, False, True])
    y_true = np.array([0, 0, 1, -1])
    ids = np.array([0, 1])
    id_to_label = {0: "Benign", 1: "DoS", -1: "Unknown_held_out"}
    _, per_class, metrics, _ = evaluate_triage(
        probabilities, sets, margin, osr_scores, osr_rejected, y_true,
        ids, id_to_label, minimum_margin=0.25,
    )
    unknown = per_class.loc[per_class.class_id == -1].iloc[0]
    assert unknown.osr_rejection_rate == 1.0
    assert unknown.analyst_escalation_rate == 1.0
    assert metrics["unknown_osr_detection_rate"] == 1.0
    assert metrics["unknown_analyst_escalation_rate"] == 1.0
    assert "unknown_detection_auroc_max_probability_baseline" in metrics
    assert "unknown_detection_auroc_evt" in metrics


def test_open_set_requires_explicit_timestamps_and_never_falls_back_to_row_order():
    x = np.vstack([np.zeros((12, 2)), np.ones((12, 2))])
    y = np.array([0] * 12 + [1] * 12)
    with pytest.raises(OpenSetError, match="requires explicit timestamps"):
        MahalanobisWeibullDetector(tail_size=5).fit(x, y)


def test_triage_escalates_when_singleton_conformal_label_disagrees_with_top1():
    probabilities = np.array([[0.1, 0.9], [0.1, 0.9]])
    # First row: class 0 is the only conformal candidate, but top-1 is class 1.
    # Second row: class 1 is both top-1 and the singleton conformal candidate.
    prediction_sets = np.array([[True, False], [False, True]])
    _, per_class, metrics, _ = evaluate_triage(
        probabilities=probabilities,
        prediction_sets=prediction_sets,
        evidence_margin=np.array([0.9, 0.9]),
        osr_scores=np.array([0.1, 0.1]),
        osr_rejected=np.array([False, False]),
        y_true=np.array([0, 1]),
        class_ids=np.array([0, 1]),
        id_to_label={0: "Benign", 1: "DoS", -1: "Unknown_held_out"},
        minimum_margin=0.25,
    )
    assert per_class.loc[per_class.class_id == 0, "autonomous_acceptance_rate"].iloc[0] == 0.0
    assert metrics["automated_coverage_rate"] == 0.5
    assert metrics["singleton_set_top1_disagreement_rows"] == 1.0
