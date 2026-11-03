from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from scipy.stats import weibull_min
from sklearn.covariance import LedoitWolf


class OpenSetError(ValueError):
    pass


@dataclass
class _ClassTail:
    class_id: int
    mean: np.ndarray
    precision: np.ndarray
    shape: float
    scale: float
    tail_count: int
    sorted_tail_fit_distances: np.ndarray
    geometry_rows: int
    tail_fit_rows: int
    log_likelihood: float
    aic: float
    descriptive_ks_distance: float
    jitter_applied_to_degenerate_tail: bool


class MahalanobisWeibullDetector:
    """Empirical class-tail anomaly score with a validation-selected threshold.

    For each known class, geometry (mean and shrinkage covariance) is estimated
    on an earlier subset of proper-training observations, while the Weibull tail
    is fitted on a later, disjoint subset of the same training period. The score
    for a test point is the minimum class-specific Weibull CDF. High scores mean
    the point is far into the fitted tail of every known class.

    This is an empirical EVT-inspired detector, not a finite-sample guarantee
    that observed distances follow an exact Weibull distribution.
    """

    def __init__(
        self,
        tail_size: int = 50,
        target_known_fpr: float = 0.05,
        geometry_fraction: float = 0.70,
        minimum_validation_group: int = 20,
    ) -> None:
        if tail_size < 5:
            raise OpenSetError("tail_size must be at least 5")
        if not 0 < target_known_fpr < 1:
            raise OpenSetError("target_known_fpr must be in (0, 1)")
        if not 0.5 <= geometry_fraction < 1:
            raise OpenSetError("geometry_fraction must be in [0.5, 1)")
        if minimum_validation_group < 2:
            raise OpenSetError("minimum_validation_group must be at least 2")
        self.tail_size = int(tail_size)
        self.target_known_fpr = float(target_known_fpr)
        self.geometry_fraction = float(geometry_fraction)
        self.minimum_validation_group = int(minimum_validation_group)
        self.tails_: dict[int, _ClassTail] = {}
        self.fitted_ = False
        self.thresholds_by_class_: dict[int, float] = {}
        self.threshold_source_by_class_: dict[int, str] = {}

    @staticmethod
    def _distance(x: np.ndarray, mean: np.ndarray, precision: np.ndarray) -> np.ndarray:
        diff = x - mean
        squared = np.einsum("ij,jk,ik->i", diff, precision, diff, optimize=True)
        return np.sqrt(np.maximum(squared, 0.0))

    @staticmethod
    def _fit_tail(
        class_id: int,
        mean: np.ndarray,
        precision: np.ndarray,
        sorted_distances: np.ndarray,
        tail_size: int,
        geometry_rows: int,
        tail_fit_rows: int,
    ) -> _ClassTail:
        tail_count = min(int(tail_size), len(sorted_distances))
        tail_values = np.maximum(sorted_distances[-tail_count:].astype(float), 1e-9)
        if len(tail_values) < 5:
            raise OpenSetError(
                f"Class {class_id} has only {len(tail_values)} tail-fit distances; at least five are required"
            )
        # Tiny deterministic jitter is used only for a numerically degenerate
        # tail; the fact that jitter was required is visible in diagnostics.
        jitter_applied = bool(np.ptp(tail_values) < 1e-9)
        if jitter_applied:
            tail_values = tail_values + np.linspace(1e-8, 1e-6, len(tail_values))
        shape, _, scale = weibull_min.fit(tail_values, floc=0)
        if not np.isfinite(shape) or not np.isfinite(scale) or shape <= 0 or scale <= 0:
            raise OpenSetError(
                f"Invalid Weibull fit for class {class_id}: shape={shape}, scale={scale}"
            )
        log_likelihood = float(
            np.sum(weibull_min.logpdf(tail_values, shape, loc=0, scale=scale))
        )
        aic = float(2 * 2 - 2 * log_likelihood)
        cdf = np.sort(weibull_min.cdf(tail_values, shape, loc=0, scale=scale))
        n = len(cdf)
        upper = np.arange(1, n + 1, dtype=float) / n - cdf
        lower = cdf - np.arange(0, n, dtype=float) / n
        descriptive_ks = float(max(np.max(upper), np.max(lower)))
        return _ClassTail(
            class_id=int(class_id),
            mean=mean.copy(),
            precision=precision.copy(),
            shape=float(shape),
            scale=float(scale),
            tail_count=int(tail_count),
            sorted_tail_fit_distances=sorted_distances.copy(),
            geometry_rows=int(geometry_rows),
            tail_fit_rows=int(tail_fit_rows),
            log_likelihood=log_likelihood,
            aic=aic,
            descriptive_ks_distance=descriptive_ks,
            jitter_applied_to_degenerate_tail=jitter_applied,
        )

    def fit(
        self,
        x_train: np.ndarray,
        y_train: np.ndarray,
        timestamps: pd.Series | np.ndarray | None = None,
    ) -> "MahalanobisWeibullDetector":
        if x_train.ndim != 2 or len(x_train) != len(y_train):
            raise OpenSetError("Training features and labels have inconsistent shapes")
        if not np.all(np.isfinite(x_train)):
            raise OpenSetError("Training features must be finite after preprocessing")
        if timestamps is None:
            raise OpenSetError(
                "OSR fitting requires explicit timestamps; input row order is never accepted as a temporal substitute"
            )
        parsed = pd.to_datetime(pd.Series(timestamps), utc=True, errors="coerce")
        if len(parsed) != len(y_train) or parsed.isna().any():
            raise OpenSetError("OSR training timestamps must be valid and match training rows")
        order_times = parsed.astype("int64").to_numpy()
        ordering_source = "global_timestamp_order_within_class"
        self.tails_.clear()
        self.geometry_rows_by_class_: dict[int, int] = {}
        self.tail_fit_rows_by_class_: dict[int, int] = {}
        self.training_order_source_ = ordering_source

        for class_value in np.unique(y_train):
            class_id = int(class_value)
            class_indices = np.where(y_train == class_value)[0]
            class_indices = class_indices[np.argsort(order_times[class_indices], kind="stable")]
            count = len(class_indices)
            if count < 10:
                raise OpenSetError(
                    f"Class {class_id} has {count} proper-training rows; at least 10 are required "
                    "for disjoint geometry and tail-fit subsets"
                )
            geometry_count = int(np.floor(count * self.geometry_fraction))
            geometry_count = min(max(geometry_count, 5), count - 5)
            geometry_indices = class_indices[:geometry_count]
            tail_indices = class_indices[geometry_count:]
            geometry = x_train[geometry_indices]
            tail_fit = x_train[tail_indices]

            estimator = LedoitWolf().fit(geometry)
            mean = geometry.mean(axis=0)
            precision = np.linalg.pinv(estimator.covariance_, hermitian=True)
            tail_distances = np.sort(self._distance(tail_fit, mean, precision))
            fitted_tail = self._fit_tail(
                class_id,
                mean,
                precision,
                tail_distances,
                self.tail_size,
                geometry_rows=len(geometry_indices),
                tail_fit_rows=len(tail_indices),
            )
            self.tails_[class_id] = fitted_tail
            self.geometry_rows_by_class_[class_id] = int(len(geometry_indices))
            self.tail_fit_rows_by_class_[class_id] = int(len(tail_indices))

        self.classes_ = np.array(sorted(self.tails_), dtype=int)
        self.fitted_ = True
        return self

    def with_tail_size(self, tail_size: int) -> "MahalanobisWeibullDetector":
        """Create a detector variant re-fitting only Weibull tails from stored distances.

        Class geometry and the tail-fit observations are identical, so the
        returned variant isolates the chosen upper-tail count.
        """
        if not self.fitted_:
            raise OpenSetError("Open-set detector must be fitted before tail-size variation")
        if tail_size < 5:
            raise OpenSetError("tail_size must be at least 5")
        variant = MahalanobisWeibullDetector(
            tail_size=tail_size,
            target_known_fpr=self.target_known_fpr,
            geometry_fraction=self.geometry_fraction,
            minimum_validation_group=self.minimum_validation_group,
        )
        for class_id, original in self.tails_.items():
            variant.tails_[class_id] = self._fit_tail(
                class_id,
                original.mean,
                original.precision,
                original.sorted_tail_fit_distances,
                tail_size,
                original.geometry_rows,
                original.tail_fit_rows,
            )
        variant.classes_ = self.classes_.copy()
        variant.geometry_rows_by_class_ = self.geometry_rows_by_class_.copy()
        variant.tail_fit_rows_by_class_ = self.tail_fit_rows_by_class_.copy()
        variant.training_order_source_ = self.training_order_source_
        variant.fitted_ = True
        return variant

    def tail_fit_diagnostics(self) -> pd.DataFrame:
        if not self.fitted_:
            raise OpenSetError("Open-set detector is not fitted")
        return pd.DataFrame(
            [
                {
                    "class_id": int(class_id),
                    "geometry_rows": tail.geometry_rows,
                    "tail_fit_rows": tail.tail_fit_rows,
                    "tail_size_requested": self.tail_size,
                    "tail_size_used": tail.tail_count,
                    "weibull_shape": tail.shape,
                    "weibull_scale": tail.scale,
                    "log_likelihood_on_fitted_tail": tail.log_likelihood,
                    "aic_on_fitted_tail": tail.aic,
                    "descriptive_ks_distance_on_fitted_tail": tail.descriptive_ks_distance,
                    "jitter_applied_to_degenerate_tail": tail.jitter_applied_to_degenerate_tail,
                }
                for class_id, tail in sorted(self.tails_.items())
            ]
        )

    def _class_tail_scores(self, x: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise OpenSetError("Open-set detector is not fitted")
        if x.ndim != 2:
            raise OpenSetError("Input features must be a 2D matrix")
        class_scores = []
        for class_id in self.classes_:
            tail = self.tails_[int(class_id)]
            distances = self._distance(x, tail.mean, tail.precision)
            cdf = weibull_min.cdf(distances, tail.shape, loc=0, scale=tail.scale)
            class_scores.append(np.clip(cdf, 0.0, 1.0))
        return np.column_stack(class_scores)

    def score_samples(self, x: np.ndarray) -> np.ndarray:
        return np.min(self._class_tail_scores(x), axis=1)

    def calibrate_threshold(
        self,
        x_validation: np.ndarray,
        y_validation: np.ndarray,
    ) -> "MahalanobisWeibullDetector":
        known = np.asarray(y_validation) >= 0
        if int(known.sum()) < 20:
            raise OpenSetError(
                "At least 20 known validation samples are required to calibrate rejection thresholds"
            )
        matrix = self._class_tail_scores(x_validation[known])
        scores = np.min(matrix, axis=1)
        nearest_columns = np.argmin(matrix, axis=1)
        nearest_classes = self.classes_[nearest_columns]
        self.thresholds_by_class_.clear()
        self.threshold_source_by_class_.clear()
        self.validation_threshold_fit_rejection_rate_by_nearest_class_: dict[int, float | None] = {}
        for class_id in self.classes_:
            selected = nearest_classes == class_id
            if int(selected.sum()) >= self.minimum_validation_group:
                threshold = float(
                    np.quantile(
                        scores[selected],
                        1.0 - self.target_known_fpr,
                        method="higher",
                    )
                )
                self.threshold_source_by_class_[int(class_id)] = (
                    "nearest-class_validation_quantile"
                )
                self.validation_threshold_fit_rejection_rate_by_nearest_class_[int(class_id)] = float(
                    np.mean(scores[selected] > threshold)
                )
            else:
                threshold = 1.0
                self.threshold_source_by_class_[int(class_id)] = (
                    "insufficient_validation_rows_no_rejection"
                )
                self.validation_threshold_fit_rejection_rate_by_nearest_class_[int(class_id)] = None
            self.thresholds_by_class_[int(class_id)] = threshold
        self.validation_known_rows_ = int(known.sum())
        self.validation_threshold_fit_rejection_rate_ = float(
            np.mean(
                [
                    scores[i] > self.thresholds_by_class_[int(nearest_classes[i])]
                    for i in range(len(scores))
                ]
            )
        )
        return self

    def reject(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if not self.thresholds_by_class_:
            raise OpenSetError(
                "Rejection thresholds must be calibrated on validation data first"
            )
        matrix = self._class_tail_scores(x)
        nearest_columns = np.argmin(matrix, axis=1)
        nearest_classes = self.classes_[nearest_columns]
        scores = matrix[np.arange(len(matrix)), nearest_columns]
        thresholds = np.array(
            [self.thresholds_by_class_[int(class_id)] for class_id in nearest_classes]
        )
        return scores, scores > thresholds
