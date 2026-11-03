import numpy as np
import pytest

from ids_reliability.conformal import ConformalError, MarginalSplitConformalPredictor

from ids_reliability.conformal import MondrianConformalPredictor


def test_class_conditional_pvalues_and_empty_stratum_are_conservative():
    p_cal = np.array([
        [0.9, 0.1, 0.0],
        [0.8, 0.2, 0.0],
        [0.7, 0.3, 0.0],
        [0.2, 0.8, 0.0],
    ])
    y_cal = np.array([0, 0, 0, 1])
    cp = MondrianConformalPredictor(alpha=0.1).fit(p_cal, y_cal, class_ids=np.array([0, 1, 2]))
    assert cp.stratum_sizes_ == {0: 3, 1: 1, 2: 0}
    p_test = np.array([[0.6, 0.3, 0.1]])
    p_values = cp.p_values(p_test)
    assert p_values[0, 2] == 1.0
    sets, margin, _ = cp.predict(p_test)
    assert sets[0, 2]
    assert 0 <= margin[0] <= 1


def test_nonrandomized_pvalue_treats_ties_as_greater_or_equal():
    p_cal = np.array([[0.8, 0.2], [0.8, 0.2], [0.6, 0.4]])
    y_cal = np.array([0, 0, 0])
    cp = MondrianConformalPredictor(0.1).fit(p_cal, y_cal, class_ids=np.array([0, 1]))
    p = cp.p_values(np.array([[0.8, 0.2]]))
    assert p[0, 0] == 1.0
    assert cp.theoretical_status()["cross_class_pooling"] is False


def test_conformal_rejects_unrepresented_labels_and_duplicate_class_ids():
    probabilities = np.array([[0.8, 0.2], [0.7, 0.3]])
    with pytest.raises(ConformalError, match="not represented"):
        MondrianConformalPredictor().fit(probabilities, np.array([0, 9]), class_ids=np.array([0, 1]))
    with pytest.raises(ConformalError, match="unique"):
        MondrianConformalPredictor().fit(probabilities, np.array([0, 1]), class_ids=np.array([0, 0]))


def test_marginal_conformal_validates_probability_rows():
    with pytest.raises(ConformalError, match="sum to one"):
        MarginalSplitConformalPredictor().fit(np.array([[0.7, 0.7]]), np.array([0]))


def test_conformal_rejects_completely_empty_calibration_set():
    with pytest.raises(ConformalError, match="at least one observation"):
        MondrianConformalPredictor().fit(np.empty((0, 2)), np.array([], dtype=int))
