#!/usr/bin/env python
"""
ML 模型训练脚本

用法:
  python scripts/train_model.py --start 2025-01-01 --end 2026-04-28
  python scripts/train_model.py --walk-forward   # walk-forward 验证
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    parser = argparse.ArgumentParser(description="Train stock prediction model")
    parser.add_argument("--start", default=None, help="Training start date")
    parser.add_argument("--end", default=None, help="Training end date")
    parser.add_argument("--horizon", type=int, default=5, help="Prediction horizon (days)")
    parser.add_argument("--walk-forward", action="store_true", help="Run walk-forward validation")
    parser.add_argument("--save", action="store_true", help="Save trained model")
    args = parser.parse_args()

    from backend.ml.features import FeatureBuilder

    if args.walk_forward:
        print("=" * 60)
        print("Walk-Forward Validation")
        print("=" * 60)
        from backend.ml.walk_forward import WalkForwardValidator
        validator = WalkForwardValidator(horizon=args.horizon)
        start = args.start or "2024-01-01"
        end = args.end or "2026-04-28"
        result = validator.validate(start, end)
        if not result.folds:
            print("Not enough data for walk-forward validation.")
            print("Need at least 140 trading dates of CP history + K-line data.")
            return
        print(result.summary())
        print("\nFold details:")
        for i, f in enumerate(result.folds, 1):
            print(f"  Fold {i}: train {f.train_start}~{f.train_end} ({f.n_train} samples) "
                  f"| test {f.test_start}~{f.test_end} ({f.n_test}) "
                  f"| MAE={f.test_mae:.4f} IC={f.test_ic:.4f}")
        return

    print("Building dataset ...")
    builder = FeatureBuilder()
    start = args.start or "2024-01-01"
    end = args.end or "2026-04-28"
    df = builder.build_dataset(start, end, args.horizon)

    if df.empty or len(df) < 100:
        print(f"Insufficient data: {len(df)} rows (need >= 100).")
        print("Ensure CP history and DuckDB K-line data cover the date range.")
        return

    print(f"Dataset: {len(df)} rows, {len(df.columns)} columns")

    from backend.ml.model import StockPredictor
    from backend.ml.features import ALL_FEATURES

    feature_cols = [c for c in ALL_FEATURES if c in df.columns]
    split = int(len(df) * 0.8)
    X_train = df.iloc[:split][feature_cols]
    y_train = df.iloc[:split]["target"]
    X_val = df.iloc[split:][feature_cols]
    y_val = df.iloc[split:]["target"]

    print(f"Train: {len(X_train)} | Val: {len(X_val)}")

    model = StockPredictor()
    metrics = model.train(X_train, y_train, X_val, y_val)

    print(f"\nTraining complete:")
    print(f"  Val MAE: {metrics.get('val_mae', 'N/A'):.4f}")
    print(f"  Val AUC: {metrics.get('val_auc', 'N/A'):.4f}")

    print("\nFeature importance (top 10):")
    imp = model.feature_importance()
    for name, score in list(imp.items())[:10]:
        bar = "#" * int(score * 50)
        print(f"  {name:<25} {score:.4f} {bar}")

    if args.save:
        model.save()
        print(f"\nModel saved to models/")


if __name__ == "__main__":
    main()
