from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler


class PreprocessingError(ValueError):
    pass


@dataclass
class TrainOnlyPreprocessor:
    feature_columns: tuple[str, ...]
    clip_limit: float = 1e15

    def __post_init__(self) -> None:
        if not self.feature_columns:
            raise PreprocessingError("At least one feature column is required")
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        self.scaler = RobustScaler()
        self.fitted_ = False
        self.audit_: dict[str, object] = {}

    def _matrix(self, frame: pd.DataFrame) -> np.ndarray:
        missing = set(self.feature_columns).difference(frame.columns)
        if missing:
            raise PreprocessingError(f"Partition is missing feature columns: {sorted(missing)}")
        values = frame.loc[:, self.feature_columns].to_numpy(dtype=np.float64, copy=True)
        values[~np.isfinite(values)] = np.nan
        values = np.clip(values, -self.clip_limit, self.clip_limit)
        return values

    def fit(self, train_frame: pd.DataFrame) -> "TrainOnlyPreprocessor":
        raw = self._matrix(train_frame)
        missing_count = int(np.isnan(raw).sum())
        self.imputer.fit(raw)
        imputed = self.imputer.transform(raw)
        self.scaler.fit(imputed)
        self.fitted_ = True
        self.audit_ = {
            "fit_partition": "train_only",
            "train_rows": int(len(train_frame)),
            "feature_count": len(self.feature_columns),
            "missing_or_nonfinite_values_imputed_in_train": missing_count,
            "clip_limit": self.clip_limit,
            "imputation_strategy": "median",
            "scaler": "RobustScaler",
        }
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        if not self.fitted_:
            raise PreprocessingError("Preprocessor must be fitted on training data before transform")
        raw = self._matrix(frame)
        return self.scaler.transform(self.imputer.transform(raw))

    def fit_transform(self, train_frame: pd.DataFrame) -> np.ndarray:
        return self.fit(train_frame).transform(train_frame)
