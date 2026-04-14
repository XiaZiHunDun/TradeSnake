# 上涨概率预测引擎 v19.8

> 本文档是 ENGINE_ARCHITECTURE.md 的补充，详细描述上涨概率预测引擎的设计。

---

## 一、概述

### 1.1 设计原则

- **完全独立**：不依赖战力评分，只使用K线数据
- **规则模型初版**：v19.8为规则模型，后续迭代升级机器学习
- **每日一次**：每日收盘后执行一次预测

### 1.2 引擎职责

预测股票未来N日上涨概率，为 recommender 提供融合决策依据。

### 1.3 触发频率

| 触发方式 | 执行时间 | 说明 |
|----------|----------|------|
| **每日定时** | 收盘后（约15:30-16:00） | 每日仅触发一次，使用当日K线数据 |

### 1.4 持久化策略

| 项目 | 说明 |
|------|------|
| **存储内容** | 每日预测结果（code, up_probability_3d, up_probability_5d, confidence, risk_level, features, timestamp） |
| **存储位置** | `data_manager/prediction_store.py`（SQLite） |
| **存储周期** | 最近90天（可配置），历史数据用于回测 |
| **数据量估算** | 200股票 × 90天 × ~1KB ≈ 18MB/年 |

### 1.5 回测支持

| 项目 | 说明 |
|------|------|
| **回测目标** | 验证概率预测准确性，评估策略有效性 |
| **回测逻辑** | 每日预测后记录，对比N日后是否实际上涨 |
| **评估指标** | 预测偏差、TopK准确率、概率校准度 |
| **回测触发** | 手动触发或每周定时 |

---

## 二、输入输出

### 输入

| 来源 | 数据内容 | 说明 |
|------|----------|------|
| data_manager | 历史日K线 | `get_klines_from_duckdb()` 获取 |

### 输出

| 输出内容 | 使用者 |
|----------|--------|
| `ProbabilityPrediction` 上涨概率 | recommender（融合决策） |
| 预测结果持久化 | data_manager/prediction_store（写入90天历史） |

### 2.1 与推荐引擎的集成

| 使用方式 | 说明 |
|----------|------|
| **融合决策** | recommender 融合战力排名和上涨概率，优先推荐"战力高+上涨概率高"的股票 |
| **过滤条件** | 过滤 up_probability_5d < 0.5 的股票 |
| **排序因子** | 可按 up_probability_5d 排序获取"最可能涨"股票 |
| **风险过滤** | 过滤 risk_level = high 的股票 |

---

## 三、目录结构

```
backend/engine/probability_predictor/
├── __init__.py
├── predictor.py               # 预测器
└── features.py              # 特征计算
```

---

## 四、数据结构

### 4.1 ProbabilityPrediction（单只股票上涨概率预测）

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 股票代码 |
| name | str | 股票名称 |
| up_probability_3d | float | 3日上涨概率 0-1 |
| up_probability_5d | float | 5日上涨概率 0-1 |
| confidence | float | 置信度 0-1 |
| risk_level | str | high/medium/low |
| features | Dict | 主要特征值 |
| model_version | str | "rule_v19.8" |

### 4.2 ProbabilityPredictionResult（批量结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| predictions | List[ProbabilityPrediction] | 预测列表 |
| calculated_at | str | 计算时间 |
| data_timestamp | str | 数据时间戳 |
| stock_count | int | 股票数量 |

---

## 五、特征计算

### 5.1 特征分类

| 类别 | 特征名 | 计算方式 |
|------|--------|----------|
| 动量 | gain_3d, gain_5d, gain_10d, gain_20d | N日收益率 |
| 波动率 | volatility_20d, atr_14 | 20日波动率、ATR指标 |
| 趋势 | ma_position | 收盘价/MA20比率 |
| 技术指标 | rsi_14, kdj_k, kdj_d, kdj_j | RSI、KDJ |
| 市场状态 | board_type, limit_type | 板块类型、涨跌停状态 |

### 5.2 缺失值处理

与 GainPredictor 相同，详见 GAIN_PREDICTOR.md

---

## 六、预测算法

### 6.1 综合得分计算

```
综合得分 = 动量得分×50% + 趋势得分×20% + RSI得分×20% + KDJ得分×10%
```

### 6.2 各因子计算逻辑

| 因子 | 计算方式 | 范围 | 说明 |
|------|----------|------|------|
| **动量得分** | (gain_3d×0.5 + gain_5d×0.3 + gain_10d×0.2) / 25 | -1 ~ +1 | 归一化到±1 |
| **趋势得分** | MA位置偏离×系数 | -0.5 ~ +0.5 | 站上MA20为正 |
| **RSI得分** | 超买超卖修正 | ±0.15 | RSI<30超卖+, RSI>70超买- |
| **KDJ得分** | 金叉死叉信号 | ±0.1 | 金叉且J>0为正 |

### 6.3 概率转换

```
上涨概率 = (综合得分 + 1) / 2
```

### 6.4 涨跌停处理

| 状态 | 处理逻辑 |
|------|----------|
| 涨停（limit_up） | `max(probability + 0.15, 0.65)`，最低0.65 |
| 跌停（limit_down） | `min(probability - 0.15, 0.25)`，最高0.25 |

### 6.5 置信度计算

```
confidence = min(0.5 + abs(综合得分) × 0.3, 0.9)
```

- 信号明确（|综合得分|高）→ 高置信度
- 信号模糊（综合得分接近0）→ 低置信度

---

## 七、风险等级计算

| 风险等级 | 条件 | 说明 |
|----------|------|------|
| high | volatility_20d > 40 | 高波动股票 |
| medium | 20 < volatility_20d <= 40 | 中等波动 |
| low | volatility_20d <= 20 | 低波动 |

---

## 八、API设计

### 8.1 端点

```
GET /api/prediction/probability/top
```

### 8.2 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 5 | 预测周期（3或5） |
| limit | int | 20 | 返回数量（1-50） |

### 8.3 响应示例

```json
{
  "predictions": [
    {
      "code": "000001",
      "name": "平安银行",
      "up_probability_3d": 0.68,
      "up_probability_5d": 0.72,
      "confidence": 0.65,
      "risk_level": "medium",
      "features": {
        "gain_3d": 3.5,
        "volatility_20d": 22.5,
        "rsi_14": 65.3
      },
      "model_version": "rule_v19.8"
    }
  ],
  "calculated_at": "2026-04-08T15:30:00",
  "data_timestamp": "2026-04-08T15:00:00",
  "stock_count": 200
}
```

---

## 九、修复清单（v19.8）

| # | 问题 | 修复方式 |
|---|------|----------|
| 1 | 概率溢出 | 增加 `max(0.0, min(1.0, ...))` |
| 2 | 涨停处理过严 | 改为偏移±0.15而非直接赋值 |
| 3 | 缺少风险等级计算 | 增加 volatility > 40/20 阈值判断 |
| 4 | 停牌/新股缺失 | 增加缺失值处理 |

---

## 十、未来扩展方向

1. **概率校准**：Platt Scaling / Isotonic Regression
2. **机器学习模型**：LightGBM/XGBoost 替代规则模型
3. **市场状态自适应**：牛市/熊市/震荡市不同权重
4. **滚动训练**：每周/每月增量更新模型
5. **特征漂移检测**：PSI指标监控

---

## 十一、验证方式

```bash
# 1. 单元测试
python -m pytest backend/tests/test_prediction_engines.py -v

# 2. API测试
curl "http://localhost:8001/api/prediction/probability/top?days=5&limit=10"
```
