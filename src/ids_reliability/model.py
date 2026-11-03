from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier


class ModelError(ValueError):
    pass


class KnownClassClassifier:
    """Single closed-set multiclass GBDT; probabilities are not assumed calibrated."""

    def __init__(self, random_state: int = 42, **parameters: object) -> None:
        allowed = {
            "max_iter", "learning_rate", "max_leaf_nodes", "l2_regularization",
            "min_samples_leaf", "class_weight", "max_bins",
        }
        unknown = set(parameters).difference(allowed)
        if unknown:
            raise ModelError(f"Unsupported classifier parameters: {sorted(unknown)}")
        self.estimator = HistGradientBoostingClassifier(
            random_state=random_state,
            early_stopping=False,
            **parameters,
        )
        self.fitted_ = False

    def fit(self, x_train: np.ndarray, y_train: np.ndarray) -> "KnownClassClassifier":
        if x_train.ndim != 2 or len(x_train) != len(y_train):
            raise ModelError("Training matrix and target dimensions do not match")
        classes, counts = np.unique(y_train, return_counts=True)
        if len(classes) < 2:
            raise ModelError("At least two known classes are required")
        if np.any(counts < 2):
            raise ModelError(f"Every known class needs at least two training examples; counts={dict(zip(classes.tolist(), counts.tolist()))}")
        self.estimator.fit(x_train, y_train)
        self.classes_ = self.estimator.classes_.astype(int)
        self.fitted_ = True
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise ModelError("Classifier is not fitted")
        return self.estimator.predict_proba(x)

    def predict(self, x: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise ModelError("Classifier is not fitted")
        return self.estimator.predict(x).astype(int)
