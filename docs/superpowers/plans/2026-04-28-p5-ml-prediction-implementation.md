# 任务：ML 预测模型（P5）

> 日期：2026-04-28  
> 类型：Strategy Upgrade（高复杂度）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：P1、P2 完成（用 P2 的因子分析确认特征选择）

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

**核心原则**：宁可训练一个简单的有效模型，也不要一个复杂的过拟合模型。Walk-forward validation 是必须的。

---

## Goal

用 LightGBM 替换规则模型（`gain_predictor` 和 `probability_predictor`），实现：

1. **特征工程模块** — 从 CP 因子 + 技术指标构建特征矩阵
2. **LightGBM 预测模型** — 预测 5 日收益率和涨跌方向
3. **Walk-forward 训练** — 滚动窗口训练+测试，避免未来信息泄露
4. **模型管理** — 训练/保存/加载/版本控制
5. **与推荐引擎集成** — 替换 `fusion_predict`

---

## Context

### 当前规则模型问题

- `gain_predictor.py`：纯线性组合（近 N 日涨幅 + RSI 修正 + MACD 修正），无学习能力
- `probability_predictor.py`：线性组合（动量 + 趋势 + RSI + KDJ），手动映射到 [0,1]
- 两者都是滞后指标的简单加权，学术上已被证明单独使用效果极弱

### ML 模型设计

```
Features (截面特征):
├── CP 因子: total_cp, growth, value, quality, momentum
├── 技术指标: RSI_14, MACD_diff, KDJ_J, MA5/10/20 斜率, 成交量比率
├── 统计特征: 5/10/20日收益率, 波动率, 偏度, 峰度
└── 市场特征: 大盘涨跌, 板块涨跌（如可获取）

Target:
├── 回归: 5日收益率 (continuous)
└── 分类: 5日涨跌方向 (binary, threshold=0%)

Validation: Walk-forward
├── 训练窗口: 120 交易日 (~6个月)
├── 测试窗口: 20 交易日 (~1个月)
├── 滚动步长: 20 交易日
└── 不使用未来信息
```

---

## Scope

Allowed changes:

- 创建 `backend/ml/` 目录（新模块）
  - `backend/ml/__init__.py`
  - `backend/ml/features.py` — 特征工程
  - `backend/ml/model.py` — 模型训练/预测
  - `backend/ml/walk_forward.py` — Walk-forward 验证
- 修改 `backend/predictor/gain_predictor.py`（添加 ML 预测路径）
- 修改 `backend/predictor/probability_predictor.py`（添加 ML 预测路径）
- 修改 `backend/recommender/recommend_engine.py`（集成 ML 预测）
- 创建 `scripts/train_model.py`（训练脚本）
- 创建 `backend/tests/test_ml_model.py`
- 修改 `requirements.txt`（添加 lightgbm、scikit-learn）

Out of scope:

- 不修改前端
- 不修改 CP 引擎核心
- 不修改 API 端点路径（只改返回数据的生成方式）

---

## Steps

### Step 1: 安装依赖

```bash
pip install lightgbm scikit-learn
```

在 `requirements.txt` 中添加：
```
lightgbm>=4.0.0
scikit-learn>=1.3.0
```

### Step 2: 创建特征工程模块

`backend/ml/features.py`:

```python
"""ML 特征工程

从 CP 因子 + K 线数据构建特征矩阵
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional


class FeatureBuilder:
    """构建股票预测特征"""
    
    # CP 因子特征
    CP_FEATURES = ['total_cp', 'growth_score', 'value_score', 
                   'quality_score', 'momentum_score', 'risk_score']
    
    # 技术指标特征
    TECHNICAL_FEATURES = [
        'rsi_14', 'macd_diff', 'macd_signal',
        'ma5_slope', 'ma10_slope', 'ma20_slope',
        'volume_ratio_5d', 'volume_ratio_10d',
    ]
    
    # 统计特征
    STAT_FEATURES = [
        'return_5d', 'return_10d', 'return_20d',
        'volatility_10d', 'volatility_20d',
        'skew_20d', 'kurtosis_20d',
    ]
    
    def __init__(self):
        from backend.data_manager.cp_history_store import get_cp_history_store
        from backend.data_manager.duckdb_store import get_duckdb_store
        self.cp_store = get_cp_history_store()
        self.duckdb = get_duckdb_store()
    
    def build_features_for_date(self, date: str, codes: List[str]) -> pd.DataFrame:
        """为某日所有股票构建特征矩阵"""
        ...
    
    def build_target(self, date: str, codes: List[str], horizon: int = 5) -> pd.Series:
        """构建目标变量（N 日收益率）"""
        ...
    
    def build_dataset(self, start_date: str, end_date: str, 
                      horizon: int = 5) -> pd.DataFrame:
        """构建完整数据集（所有日期 × 所有股票）"""
        ...
    
    def _compute_rsi(self, closes: np.ndarray, period: int = 14) -> float:
        """计算 RSI"""
        ...
    
    def _compute_macd(self, closes: np.ndarray) -> tuple:
        """计算 MACD"""
        ...
```

### Step 3: 创建模型模块

`backend/ml/model.py`:

```python
"""LightGBM 预测模型"""
import lightgbm as lgb
import numpy as np
import pandas as pd
import json
import os
from typing import Dict, Optional
from datetime import datetime


class StockPredictor:
    """股票收益预测模型
    
    两个子模型：
    - 回归模型：预测 5 日收益率
    - 分类模型：预测 5 日涨跌方向
    """
    
    MODEL_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models')
    
    # LightGBM 参数（偏保守，避免过拟合）
    REGRESSION_PARAMS = {
        'objective': 'regression',
        'metric': 'mae',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 20,
        'lambda_l1': 0.1,
        'lambda_l2': 0.1,
        'verbose': -1,
    }
    
    CLASSIFIER_PARAMS = {
        'objective': 'binary',
        'metric': 'auc',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 20,
        'lambda_l1': 0.1,
        'lambda_l2': 0.1,
        'verbose': -1,
    }
    
    NUM_BOOST_ROUND = 200
    EARLY_STOPPING_ROUNDS = 20
    
    def __init__(self):
        self.reg_model = None
        self.cls_model = None
        self.feature_names = None
        self.train_date = None
    
    def train(self, X_train, y_train, X_val=None, y_val=None):
        """训练回归 + 分类模型"""
        ...
    
    def predict_return(self, X) -> np.ndarray:
        """预测收益率"""
        ...
    
    def predict_direction(self, X) -> np.ndarray:
        """预测涨跌概率"""
        ...
    
    def save(self, version: str = None):
        """保存模型"""
        ...
    
    def load(self, version: str = 'latest'):
        """加载模型"""
        ...
    
    def feature_importance(self) -> Dict[str, float]:
        """返回特征重要性"""
        ...
```

### Step 4: 创建 Walk-forward 验证

`backend/ml/walk_forward.py`:

```python
"""Walk-forward 验证框架

避免未来信息泄露的模型验证
"""


class WalkForwardValidator:
    """滚动窗口训练+测试"""
    
    def __init__(self, 
                 train_window: int = 120,
                 test_window: int = 20,
                 step_size: int = 20):
        self.train_window = train_window  # 训练窗口（交易日）
        self.test_window = test_window    # 测试窗口
        self.step_size = step_size        # 滚动步长
    
    def validate(self, feature_builder, start_date, end_date):
        """运行 walk-forward 验证
        
        Returns:
            Dict with:
            - oos_predictions: 样本外预测结果
            - oos_returns: 实际收益
            - metrics_per_fold: 每个 fold 的指标
            - aggregate_metrics: 汇总指标
        """
        ...
    
    def _generate_folds(self, dates):
        """生成训练/测试日期分割"""
        ...
```

### Step 5: 创建训练脚本

`scripts/train_model.py`:

```python
"""
模型训练脚本
运行: python scripts/train_model.py [--start 2024-01-01] [--end 2026-04-28]

输出：
1. models/ 目录下的模型文件
2. Walk-forward 验证报告
3. 特征重要性排名
"""
```

### Step 6: 集成到预测引擎

修改 `gain_predictor.py` 和 `probability_predictor.py`：

```python
def predict(self, code, ...):
    # 尝试使用 ML 模型
    try:
        from backend.ml.model import StockPredictor
        predictor = StockPredictor()
        predictor.load('latest')
        if predictor.reg_model is not None:
            features = self._build_features(code)
            return predictor.predict_return(features)
    except Exception:
        pass  # ML 模型不可用时回退到规则模型
    
    # 回退到原有规则模型
    return self._rule_based_predict(code, ...)
```

**关键**：保持向后兼容。ML 模型不存在时自动回退到规则模型。

### Step 7: 测试

- [ ] 创建 `backend/tests/test_ml_model.py`：
  - 测试特征构建
  - 测试模型训练/预测/保存/加载（用小数据集）
  - 测试 walk-forward 分割逻辑
  - 测试 ML → 规则模型回退
- [ ] 全量回归测试

---

## Verification

```bash
# 模块导入
python -c "from backend.ml.features import FeatureBuilder; print('OK')"
python -c "from backend.ml.model import StockPredictor; print('OK')"

# 训练脚本帮助
python scripts/train_model.py --help

# 既有测试
python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py

# ML 专属测试
python -m pytest backend/tests/test_ml_model.py -v
```

---

## Stop Conditions

1. `pip install lightgbm` 失败 → 报告环境问题
2. CP history 数据少于 120 天 → 模型可以构建但标记"数据不足以训练"
3. Walk-forward 显示 ML 模型不比规则模型好 → 仍然保留 ML 架构，但默认使用规则模型

---

## Completion Report Format

```markdown
## Summary
- 创建的模块
- 模型架构说明

## Walk-forward Results（如有数据）
- 样本外 MAE / AUC
- 与规则模型的对比

## Feature Importance
- Top 10 重要特征

## Integration
- ML 回退机制说明
- 如何训练新模型

## Verification
- 测试结果
```
