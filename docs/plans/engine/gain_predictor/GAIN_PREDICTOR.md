# 涨幅预测引擎 v19.8

> 本文档是 ENGINE_ARCHITECTURE.md 的补充，详细描述涨幅预测引擎的设计。

---

## 一、概述

### 1.1 设计原则

- **完全独立**：不依赖战力评分，只使用K线数据
- **规则模型初版**：v19.8为规则模型，后续迭代升级机器学习
- **每日一次**：每日收盘后执行一次预测

### 1.2 引擎职责

预测股票未来N日涨幅，为 recommender 提供融合决策依据。

### 1.3 触发频率

| 触发方式 | 执行时间 | 说明 |
|----------|----------|------|
| **每日定时** | 收盘后（约15:30-16:00） | 每日仅触发一次，使用当日K线数据 |

### 1.4 持久化策略

| 项目 | 说明 |
|------|------|
| **存储内容** | 每日预测结果（code, predicted_gain_3d, predicted_gain_5d, confidence, features, timestamp） |
| **存储位置** | `data_manager/prediction_store.py`（SQLite） |
| **存储周期** | 最近90天（可配置），历史数据用于回测 |
| **数据量估算** | 200股票 × 90天 × ~1KB ≈ 18MB/年 |

### 1.5 回测支持

| 项目 | 说明 |
|------|------|
| **回测目标** | 验证预测准确性，评估策略有效性 |
| **回测逻辑** | 每日预测后记录，对比N日后实际涨幅 |
| **评估指标** | 预测偏差、TopK准确率、累计收益、夏普比率 |
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
| `GainPrediction` 涨幅预测 | recommender（融合决策） |
| 预测结果持久化 | data_manager/prediction_store（写入90天历史） |

### 2.1 与推荐引擎的集成

| 使用方式 | 说明 |
|----------|------|
| **融合决策** | recommender 融合战力排名和涨幅预测，优先推荐"战力高+预测涨幅高"的股票 |
| **过滤条件** | 过滤 predicted_gain_5d < 0 的股票 |
| **排序因子** | 可按 predicted_gain_5d 排序获取"潜在涨幅最大"股票 |
| **置信加权** | 高置信度预测可获得更高权重 |

---

## 三、目录结构

```
backend/engine/gain_predictor/
├── __init__.py
├── predictor.py               # 预测器
└── features.py               # 特征计算
```

---

## 四、数据结构

### 4.1 GainPrediction（单只股票涨幅预测）

| 字段 | 类型 | 说明 |
|------|------|------|
| code | str | 股票代码 |
| name | str | 股票名称 |
| predicted_gain_3d | float | 预测3日涨幅% |
| predicted_gain_5d | float | 预测5日涨幅% |
| confidence | float | 置信度 0-1 |
| confidence_interval_3d | Tuple | 3日置信区间 |
| confidence_interval_5d | Tuple | 5日置信区间 |
| features | Dict | 主要特征值 |
| model_version | str | "rule_v19.8" |

### 4.2 GainPredictionResult（批量结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| predictions | List[GainPrediction] | 预测列表 |
| calculated_at | str | 计算时间 |
| data_timestamp | str | 数据时间戳 |
| stock_count | int | 股票数量 |
| distribution | Dict | 预测分布统计 |
| avg_confidence | float | 平均置信度 |

---

## 五、特征计算

### 5.1 特征分类

| 类别 | 特征名 | 计算方式 |
|------|--------|----------|
| 动量 | gain_3d, gain_5d, gain_10d | N日收益率 |
| 波动率 | volatility_20d, atr_14 | 20日波动率、ATR指标 |
| 趋势 | ma_position | 收盘价/MA20比率 |
| 技术指标 | rsi_14, macd, macd_signal | RSI、MACD |
| 市场状态 | board_type, limit_type | 板块类型、涨跌停状态 |

### 5.2 板块涨跌幅限制

| 板块 | 代码前缀 | 涨跌幅限制 |
|------|----------|------------|
| 主板 | 000/600/601等 | 10% |
| 创业板 | 300 | 20% |
| 科创板 | 688 | 20% |
| 北交所 | 8开头 | 30% |

### 5.3 缺失值处理

| 情况 | 处理方式 |
|------|----------|
| 停牌/新股数据不足 | 标记features_missing，返回基础预测 |
| 短期特征缺失 | 用可用数据计算，不强制要求20日 |
| 长期特征缺失（如volatility_20d） | 用全局均值GLOBAL_AVG_VOLATILITY填充 |

---

## 六、预测算法

### 6.1 综合预测公式

```
predicted = 动量因子 × 波动率调整 + 趋势加成 + RSI调整 + MACD调整
```

### 6.2 各因子计算逻辑

| 因子 | 计算方式 | 贡献范围 | 说明 |
|------|----------|----------|------|
| **动量** | gain_3d×0.4 + gain_5d×0.3 + gain_10d×0.3 | 主贡献 | 加权多日涨幅 |
| **波动率调整** | min(volatility/30, 1.5) | 倍数 | 高波动放大预测幅度 |
| **趋势加成** | MA位置偏离×10 | ±2% | 站上MA20以上为正 |
| **RSI调整** | 超买超卖修正 | ±1.5% | RSI<30超卖+, RSI>70超买- |
| **MACD调整** | 金叉死叉信号 | ±1.0% | DIF>DEA且柱状图为正 |

### 6.3 涨跌停处理

| 状态 | 处理逻辑 |
|------|----------|
| 涨停（limit_up） | 预测涨幅限制max(predicted, 5%)，避免过度乐观 |
| 跌停（limit_down） | 预测涨幅限制min(predicted, -3%)，避免过度悲观 |
| 正常 | 截断到板块涨跌幅限制范围内 |

### 6.4 置信度计算

```
confidence = min(0.6 + 0.4 × (1 - volatility/50), 0.95)
interval_width = volatility × 0.4 × confidence
```

- 低波动 → 高置信度（上限0.95）
- 高波动 → 低置信度（下限0.6）

---

## 七、API设计

### 7.1 端点

```
GET /api/prediction/gain/top
```

### 7.2 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 5 | 预测周期（3或5） |
| limit | int | 20 | 返回数量（1-50） |
| fields | str | all | 指定返回特征 |

### 7.3 响应示例

```json
{
  "predictions": [
    {
      "code": "000001",
      "name": "平安银行",
      "predicted_gain_3d": 5.2,
      "predicted_gain_5d": 8.7,
      "confidence": 0.75,
      "confidence_interval_3d": [3.5, 6.9],
      "confidence_interval_5d": [6.2, 11.2],
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
  "stock_count": 200,
  "avg_confidence": 0.72
}
```

---

## 八、修复清单（v19.8）

| # | 问题 | 修复方式 |
|---|------|----------|
| 1 | 维度不一致 | 统一为百分比贡献，趋势/MA调整最多±2% |
| 2 | 涨停处理过严 | 改为偏移±0.15而非直接赋值 |
| 3 | 置信区间无依据 | 改为 `volatility × 0.4 × confidence` |
| 4 | 停牌/新股缺失 | 增加缺失值处理，用全局均值填充 |
| 5 | 板块限制硬编码 | 改为映射表（BOARD_LIMIT_CONFIG） |
| 6 | 缺少触发频率 | 补充"每日收盘后触发一次" |

---

## 九、未来扩展方向

1. **机器学习模型**：LightGBM/XGBoost 替代规则模型
2. **市场状态自适应**：牛市/熊市/震荡市不同权重
3. **滚动训练**：每周/每月增量更新模型
4. **特征漂移检测**：PSI指标监控

---

## 十、验证方式

```bash
# 1. 单元测试
python -m pytest backend/engine/gain_predictor/tests/ -v

# 2. API测试
curl "http://localhost:8001/api/prediction/gain/top?days=5&limit=10"
```
