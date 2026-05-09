"""LightGBM 股票收益预测模型

两个子模型：
- 回归：预测 5 日收益率
- 分类：预测 5 日涨跌方向

训练/保存/加载/版本管理。
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import lightgbm as lgb
import numpy as np
import pandas as pd

from backend.ml.features import ALL_FEATURES, CP_FEATURES

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"


# ── hyper-parameters (conservative to avoid overfit) ─────

_REG_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "min_child_samples": 20,
    "lambda_l1": 0.1,
    "lambda_l2": 0.1,
    "verbose": -1,
}

_CLS_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "min_child_samples": 20,
    "lambda_l1": 0.1,
    "lambda_l2": 0.1,
    "verbose": -1,
}

NUM_BOOST_ROUND = 200
EARLY_STOPPING_ROUNDS = 20


class StockPredictor:
    """LightGBM 股票预测器"""

    def __init__(self):
        self.reg_model: Optional[lgb.Booster] = None
        self.cls_model: Optional[lgb.Booster] = None
        self.feature_names: List[str] = list(ALL_FEATURES)
        self.train_date: Optional[str] = None

    @property
    def is_trained(self) -> bool:
        return self.reg_model is not None

    # ── train ───────────────────────────────────────────

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> Dict:
        """训练回归 + 分类模型，返回验证指标"""
        feature_cols = [c for c in ALL_FEATURES if c in X_train.columns]
        self.feature_names = feature_cols

        Xt = X_train[feature_cols].values
        yt = y_train.values.astype(float)

        train_reg = lgb.Dataset(Xt, label=yt, feature_name=feature_cols)
        valid_sets_reg = [train_reg]
        if X_val is not None and y_val is not None:
            Xv = X_val[feature_cols].values
            yv = y_val.values.astype(float)
            valid_sets_reg.append(lgb.Dataset(Xv, label=yv, reference=train_reg))

        callbacks = [lgb.log_evaluation(period=0)]
        if X_val is not None:
            callbacks.append(lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False))

        self.reg_model = lgb.train(
            _REG_PARAMS,
            train_reg,
            num_boost_round=NUM_BOOST_ROUND,
            valid_sets=valid_sets_reg,
            callbacks=callbacks,
        )

        y_cls_train = (yt > 0).astype(int)
        train_cls = lgb.Dataset(Xt, label=y_cls_train, feature_name=feature_cols)
        valid_sets_cls = [train_cls]
        callbacks_cls = [lgb.log_evaluation(period=0)]
        if X_val is not None and y_val is not None:
            y_cls_val = (yv > 0).astype(int)
            valid_sets_cls.append(lgb.Dataset(Xv, label=y_cls_val, reference=train_cls))
            callbacks_cls.append(lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False))

        self.cls_model = lgb.train(
            _CLS_PARAMS,
            train_cls,
            num_boost_round=NUM_BOOST_ROUND,
            valid_sets=valid_sets_cls,
            callbacks=callbacks_cls,
        )

        self.train_date = datetime.now().strftime("%Y-%m-%d")

        metrics = {"reg_best_iter": self.reg_model.best_iteration,
                   "cls_best_iter": self.cls_model.best_iteration}
        if X_val is not None:
            preds = self.reg_model.predict(Xv)
            metrics["val_mae"] = float(np.mean(np.abs(preds - yv)))
            cls_preds = self.cls_model.predict(Xv)
            from sklearn.metrics import roc_auc_score
            try:
                metrics["val_auc"] = float(roc_auc_score((yv > 0).astype(int), cls_preds))
            except ValueError:
                metrics["val_auc"] = 0.5

        return metrics

    # ── predict ─────────────────────────────────────────

    def predict_return(self, X: pd.DataFrame) -> np.ndarray:
        if self.reg_model is None:
            raise RuntimeError("Model not trained")
        cols = [c for c in self.feature_names if c in X.columns]
        return self.reg_model.predict(X[cols].values)

    def predict_direction(self, X: pd.DataFrame) -> np.ndarray:
        if self.cls_model is None:
            raise RuntimeError("Model not trained")
        cols = [c for c in self.feature_names if c in X.columns]
        return self.cls_model.predict(X[cols].values)

    # ── persistence ─────────────────────────────────────

    def save(self, version: Optional[str] = None):
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        ver = version or datetime.now().strftime("%Y%m%d_%H%M%S")
        base = MODEL_DIR / ver
        base.mkdir(exist_ok=True)
        if self.reg_model:
            self.reg_model.save_model(str(base / "reg.txt"))
        if self.cls_model:
            self.cls_model.save_model(str(base / "cls.txt"))
        meta = {
            "version": ver,
            "train_date": self.train_date,
            "feature_names": self.feature_names,
        }
        (base / "meta.json").write_text(json.dumps(meta, indent=2))
        (MODEL_DIR / "latest.txt").write_text(ver)

    def load(self, version: str = "latest") -> bool:
        if version == "latest":
            latest_file = MODEL_DIR / "latest.txt"
            if not latest_file.exists():
                return False
            version = latest_file.read_text().strip()

        base = MODEL_DIR / version
        if not base.exists():
            return False

        meta_path = base / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            self.feature_names = meta.get("feature_names", list(ALL_FEATURES))
            self.train_date = meta.get("train_date")

        reg_path = base / "reg.txt"
        if reg_path.exists():
            self.reg_model = lgb.Booster(model_file=str(reg_path))

        cls_path = base / "cls.txt"
        if cls_path.exists():
            self.cls_model = lgb.Booster(model_file=str(cls_path))

        return self.reg_model is not None

    # ── feature importance ──────────────────────────────

    def feature_importance(self) -> Dict[str, float]:
        if self.reg_model is None:
            return {}
        imp = self.reg_model.feature_importance(importance_type="gain")
        names = self.reg_model.feature_name()
        total = imp.sum() or 1
        return {n: float(v / total) for n, v in sorted(zip(names, imp), key=lambda x: -x[1])}
