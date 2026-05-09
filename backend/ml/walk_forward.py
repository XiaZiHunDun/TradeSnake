"""Walk-forward 验证框架

滚动窗口训练+测试，严格避免前瞻偏差。
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.ml.model import StockPredictor
from backend.ml.features import FeatureBuilder, ALL_FEATURES


@dataclass
class FoldResult:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    val_mae: float
    val_auc: float
    test_mae: float
    test_ic: float
    n_train: int
    n_test: int


@dataclass
class WalkForwardResult:
    folds: List[FoldResult] = field(default_factory=list)
    aggregate_mae: float = 0.0
    aggregate_ic: float = 0.0
    aggregate_auc: float = 0.0

    def summary(self) -> str:
        lines = [
            f"Walk-Forward: {len(self.folds)} folds",
            f"  Avg OOS MAE : {self.aggregate_mae:.4f}",
            f"  Avg OOS IC  : {self.aggregate_ic:.4f}",
            f"  Avg OOS AUC : {self.aggregate_auc:.4f}",
        ]
        return "\n".join(lines)


class WalkForwardValidator:
    """滚动窗口 ML 验证"""

    def __init__(
        self,
        train_window: int = 120,
        test_window: int = 20,
        step_size: int = 20,
        horizon: int = 5,
    ):
        self.train_window = train_window
        self.test_window = test_window
        self.step_size = step_size
        self.horizon = horizon

    def validate(
        self, start_date: str, end_date: str
    ) -> WalkForwardResult:
        builder = FeatureBuilder()
        dates = builder._get_trading_dates(start_date, end_date)
        if len(dates) < self.train_window + self.test_window:
            return WalkForwardResult()

        folds = self._generate_folds(dates)
        results = WalkForwardResult()

        for train_dates, test_dates in folds:
            fold = self._run_fold(builder, train_dates, test_dates)
            if fold is not None:
                results.folds.append(fold)

        if results.folds:
            results.aggregate_mae = float(np.mean([f.test_mae for f in results.folds]))
            results.aggregate_ic = float(np.mean([f.test_ic for f in results.folds]))
            aucs = [f.val_auc for f in results.folds if f.val_auc > 0]
            results.aggregate_auc = float(np.mean(aucs)) if aucs else 0.0

        return results

    def _generate_folds(self, dates: List[str]):
        folds = []
        i = 0
        while i + self.train_window + self.test_window <= len(dates):
            train = dates[i: i + self.train_window]
            test = dates[i + self.train_window: i + self.train_window + self.test_window]
            folds.append((train, test))
            i += self.step_size
        return folds

    def _run_fold(
        self,
        builder: FeatureBuilder,
        train_dates: List[str],
        test_dates: List[str],
    ) -> Optional[FoldResult]:
        train_start, train_end = train_dates[0], train_dates[-1]
        test_start, test_end = test_dates[0], test_dates[-1]

        train_df = builder.build_dataset(train_start, train_end, self.horizon)
        test_df = builder.build_dataset(test_start, test_end, self.horizon)

        if train_df.empty or len(train_df) < 50 or test_df.empty:
            return None

        feature_cols = [c for c in ALL_FEATURES if c in train_df.columns and c in test_df.columns]
        if not feature_cols:
            return None

        split = int(len(train_df) * 0.8)
        X_train = train_df.iloc[:split][feature_cols]
        y_train = train_df.iloc[:split]["target"]
        X_val = train_df.iloc[split:][feature_cols]
        y_val = train_df.iloc[split:]["target"]

        model = StockPredictor()
        metrics = model.train(X_train, y_train, X_val, y_val)

        X_test = test_df[feature_cols]
        y_test = test_df["target"].values

        preds = model.predict_return(X_test)
        test_mae = float(np.mean(np.abs(preds - y_test)))

        from scipy.stats import spearmanr
        if len(preds) > 5:
            ic, _ = spearmanr(preds, y_test)
            test_ic = float(ic) if not np.isnan(ic) else 0.0
        else:
            test_ic = 0.0

        return FoldResult(
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            val_mae=metrics.get("val_mae", 0.0),
            val_auc=metrics.get("val_auc", 0.5),
            test_mae=test_mae,
            test_ic=test_ic,
            n_train=len(train_df),
            n_test=len(test_df),
        )
