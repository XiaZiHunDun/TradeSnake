# ML 模块架构

## 目录结构

```
backend/ml/
├── __init__.py
├── features.py       # FeatureBuilder - 特征构建（CP快照 + K线技术指标）
├── model.py         # StockPredictor - LightGBM 模型封装
├── walk_forward.py  # WalkForwardValidator - 滚动窗口验证
└── _get_codes_for_date()  # 从 CP history 或 DuckDB fallback 获取股票列表
```

## 核心类

### FeatureBuilder

构建训练数据集，将 K 线数据转为技术因子特征。

**数据源**：
1. CP 历史快照：`cp_store.get_snapshot(date)` → 返回当日 CP 评分（growth/value/quality/momentum）
2. K 线数据：`duckdb.get_klines_bulk_for_date(codes, end_date, days)` → 行情数据
3. Fallback：`daily_kline` 直接查询 + LIMIT 500

**特征列表** (`ALL_FEATURES`，共 20 个 = CP 6 + 技术 8 + 统计 6)：

| 类别 | 特征 | 说明 |
|------|------|------|
| CP (6) | `total_cp`, `growth_score`, `value_score`, `quality_score`, `momentum_score`, `risk_score` | 战力体系快照 |
| 技术 (8) | `rsi_14` | 14日RSI |
| | `macd_diff`, `macd_signal` | MACD 差值与信号线 |
| | `ma5_slope`, `ma10_slope`, `ma20_slope` | 均线斜率 (%) |
| | `volume_ratio_5d`, `volume_ratio_10d` | 量比（短期/中期） |
| 统计 (6) | `return_5d`, `return_10d`, `return_20d` | 收益率 |
| | `volatility_10d`, `volatility_20d` | 波动率（年化） |
| | `skew_20d` | 收益分布偏度 |

**关键方法**：
- `build_dataset(start, end, horizon)` → 生成训练集
- `build_target(date, codes, horizon)` → 构建 N 日后收益率目标
- `_get_codes_for_date(date)` → 获取当日可交易股票列表

### StockPredictor

基于 LightGBM 的回归模型。

**训练接口**：`train(X_train, y_train, X_val, y_val)` → `{"val_mae", "val_auc"}`
**预测接口**：`predict_return(X)` → 返回预测收益率

**模型参数**（默认）：
- objective: `"regression"`
- n_estimators: 100
- learning_rate: 0.05
- max_depth: 6

### WalkForwardValidator

滚动窗口验证，避免前瞻偏差。

**窗口配置**：
- train_window: 120 天
- test_window: 20 天
- step_size: 20 天

**验证流程**：
1. 按窗口滚动切割 train/test
2. 在 train 上训练，80/20 分割做验证
3. 在 test 上做 OOS 测试
4. 输出 MAE、IC、AUC 指标

## 数据依赖

```
features.py
├── cp_store.get_snapshot()     → backend.data_manager.cp_history_store
├── duckdb.get_klines_bulk_for_date()  → backend.data_manager.duckdb_store
└── _get_codes_for_date() fallback    → daily_kline LIMIT 500

model.py
└── lightgbm
```

## 与 CP 战力体系的关系

ML 特征构建时通过 `cp_store.get_snapshot()` 获取 CP 战力因子作为特征输入（`total_cp`, `growth_score`, `value_score`, `quality_score`, `momentum_score`, `risk_score`），实现与战力体系的对接。

## 已知 Limitations

1. **技术因子 IC 已验证**：macd_diff IC=+0.0185(t=7.26)，为最强技术 alpha（来源：v21 Alpha 分析）
2. **模型预测能力弱**：AUC≈0.506，几乎随机
3. **walk_forward 训练慢**：每个 fold 需要构建大量特征