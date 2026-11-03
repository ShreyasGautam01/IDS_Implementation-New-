from __future__ import annotations

import numpy as np


class ConformalError(ValueError):
    pass


class MondrianConformalPredictor:
    """Non-randomized class-conditional split conformal prediction.

    No cross-class pooling is performed. An empty calibration stratum receives
    p-value 1 for that candidate label, yielding conservative inclusion rather
    than an unsupported transfer of another class's calibration scores.
    """

    def __init__(self, alpha: float = 0.10) -> None:
        if not 0 < alpha < 1:
            raise ConformalError("alpha must be in (0, 1)")
        self.alpha = float(alpha)
        self.calibration_scores_: dict[int, np.ndarray] = {}
        self.fitted_ = False

    @staticmethod
    def _validate_probabilities(probabilities: np.ndarray, expected_columns: int | None = None) -> None:
        if probabilities.ndim != 2 or (expected_columns is not None and probabilities.shape[1] != expected_columns):
            raise ConformalError("Probability matrix has an incompatible shape")
        if not np.all(np.isfinite(probabilities)) or np.any(probabilities < 0) or np.any(probabilities > 1):
            raise ConformalError("Probabilities must be finite and lie in [0, 1]")
        if len(probabilities) and not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-5):
            raise ConformalError("Each probability row must sum to one")

    @staticmethod
    def _validate_classes(class_ids: np.ndarray, y_calibration: np.ndarray, columns: int) -> np.ndarray:
        ids = np.asarray(class_ids, dtype=int)
        if ids.ndim != 1 or len(ids) != columns or len(ids) == 0:
            raise ConformalError("class_ids must be a non-empty vector matching probability columns")
        if len(np.unique(ids)) != len(ids):
            raise ConformalError("class_ids must be unique")
        unknown = sorted(set(np.asarray(y_calibration, dtype=int).tolist()) - set(ids.tolist()))
        if unknown:
            raise ConformalError(f"Calibration labels are not represented by model classes: {unknown}")
        return ids

    def fit(self, probabilities: np.ndarray, y_calibration: np.ndarray, class_ids: np.ndarray | None = None) -> "MondrianConformalPredictor":
        if probabilities.ndim != 2 or len(probabilities) != len(y_calibration):
            raise ConformalError("Calibration probability matrix and labels have inconsistent shapes")
        self._validate_probabilities(probabilities)
        if len(probabilities) == 0:
            raise ConformalError("Calibration set must contain at least one observation")
        self.class_ids_ = self._validate_classes(
            class_ids if class_ids is not None else np.arange(probabilities.shape[1]),
            y_calibration,
            probabilities.shape[1],
        )
        self.calibration_scores_ = {}
        for column, class_id in enumerate(self.class_ids_):
            selected = np.asarray(y_calibration) == class_id
            scores = 1.0 - probabilities[selected, column]
            self.calibration_scores_[int(class_id)] = np.sort(scores.astype(float))
        self.stratum_sizes_ = {c: int(len(s)) for c, s in self.calibration_scores_.items()}
        self.fitted_ = True
        return self

    def p_values(self, probabilities: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise ConformalError("Conformal predictor is not fitted")
        self._validate_probabilities(probabilities, len(self.class_ids_))
        n = len(probabilities)
        p_values = np.ones((n, len(self.class_ids_)), dtype=float)
        for column, class_id in enumerate(self.class_ids_):
            scores = self.calibration_scores_[int(class_id)]
            # Non-randomized p-value: ties are counted as >=, making the test conservative.
            candidate = 1.0 - probabilities[:, column]
            if len(scores) == 0:
                p_values[:, column] = 1.0
            else:
                index = np.searchsorted(scores, candidate, side="left")
                greater_or_equal = len(scores) - index
                p_values[:, column] = (1.0 + greater_or_equal) / (len(scores) + 1.0)
        return p_values

    def predict(self, probabilities: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        p_values = self.p_values(probabilities)
        prediction_sets = p_values > self.alpha
        ordered = np.sort(p_values, axis=1)
        margin = ordered[:, -1] - ordered[:, -2] if ordered.shape[1] >= 2 else ordered[:, -1]
        return prediction_sets, margin, p_values

    def theoretical_status(self) -> dict[str, object]:
        return {
            "method": "non_randomized_class_conditional_split_conformal",
            "cross_class_pooling": False,
            "empty_stratum_policy": "include_candidate_class_conservatively",
            "formal_guarantee_requires": "exchangeability of calibration and test observations within each class",
            "temporal_shift_interpretation": "empirical_coverage_only_unless_exchangeability_is_justified",
            "stratum_sizes": self.stratum_sizes_,
        }


class MarginalSplitConformalPredictor:
    """Pooled split-conformal baseline using the same nonconformity score."""

    def __init__(self, alpha: float = 0.10) -> None:
        if not 0 < alpha < 1:
            raise ConformalError("alpha must be in (0, 1)")
        self.alpha = float(alpha)
        self.fitted_ = False

    def fit(self, probabilities: np.ndarray, y_calibration: np.ndarray, class_ids: np.ndarray | None = None) -> "MarginalSplitConformalPredictor":
        if probabilities.ndim != 2 or len(probabilities) != len(y_calibration):
            raise ConformalError("Calibration probability matrix and labels have inconsistent shapes")
        MondrianConformalPredictor._validate_probabilities(probabilities)
        if len(probabilities) == 0:
            raise ConformalError("Calibration set must contain at least one observation")
        self.class_ids_ = MondrianConformalPredictor._validate_classes(
            class_ids if class_ids is not None else np.arange(probabilities.shape[1]),
            y_calibration,
            probabilities.shape[1],
        )
        column_by_id = {int(class_id): col for col, class_id in enumerate(self.class_ids_)}
        try:
            true_columns = np.array([column_by_id[int(label)] for label in y_calibration], dtype=int)
        except KeyError as exc:
            raise ConformalError(f"Calibration label {exc.args[0]} is not a known model class") from exc
        scores = 1.0 - probabilities[np.arange(len(probabilities)), true_columns]
        scores = np.sort(scores.astype(float))
        n = len(scores)
        if n == 0:
            self.quantile_ = float("inf")
        else:
            rank = int(np.ceil((n + 1) * (1.0 - self.alpha)))
            self.quantile_ = float("inf") if rank > n else float(scores[rank - 1])
        self.calibration_size_ = int(n)
        self.fitted_ = True
        return self

    def predict(self, probabilities: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise ConformalError("Marginal conformal predictor is not fitted")
        MondrianConformalPredictor._validate_probabilities(probabilities, len(self.class_ids_))
        return (1.0 - probabilities) <= self.quantile_
