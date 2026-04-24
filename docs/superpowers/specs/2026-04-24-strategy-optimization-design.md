# 策略优化设计文档

> **目标**：建立系统的策略评测和优化流程，验证稳健型策略（集中持仓、高胜率）在 2024-2025 年数据上的表现。

---

## 一、策略现状

### 1.1 战力公式权重（v19.6）

| 因子 | 权重 | 说明 |
|------|------|------|
| growth | 30% | 成长分 |
| value | 25% | 价值分 |
| quality | 20% | 质量分 |
| momentum | 8% | 动量分 |
| real_time | 2% | 实时因子 |
| risk_penalty | 10% | 风险惩罚 |

### 1.2 融合公式（PredictionFusion）

```
fused_score = 0.4 * cp_score + 0.35 * gain_score + 0.25 * prob_score
```

风控偏好（balanced）：
- cp=0.4, gain=0.35, prob=0.25

### 1.3 回测参数

| 参数 | 当前值 |
|------|--------|
| 止损线 | -3% |
| 最大持仓天数 | 5 |
| 大盘过滤阈值 | -2% |
| 最小交易金额 | 50,000 |

### 1.4 现有策略类型

| 策略 | 逻辑 |
|------|------|
| TopNStrategy | 按战力总分排序取 TOP N |
| MultiFactorStrategy | 多因子加权: growth×0.3 + value×0.25 + momentum×0.25 + quality×0.2 |
| MomentumStrategy | 按动量分排序 |
| GrowthStrategy | 按成长分排序 |
| RisingCPStrategy | 只选 cp_change > 0 的股票 |
| HybridRisingStrategy | cp_rank×0.4 + change_rank×0.6 |

---

## 二、优化目标

**类型**：稳健型策略
**持仓**：5-8 只，集中持仓（单只仓位 8-15%）
**止损**：-10%
**最大回撤容忍**：15%
**核心指标**：胜率、盈亏比

---

## 三、优化流程

### 阶段 1：策略对比

**目标**：在相同参数条件下（集中持仓、止损-10%），对比 6 种策略的表现。

**回测配置**：
- 持仓数量：5-8 只
- 止损：-10%
- 最大持仓天数：5
- 资金：初始 100 万
- 基准：沪深300

**测试策略**：
1. TopNStrategy（纯战力）
2. MultiFactorStrategy（多因子加权）
3. MomentumStrategy（纯动量）
4. GrowthStrategy（纯成长）
5. RisingCPStrategy（战力变化）
6. HybridRisingStrategy（混合）

**评估指标**：
- 年化收益率
- 最大回撤
- 夏普比率
- 卡玛比率
- 胜率
- 盈亏比
- 总交易次数

**输出**：最优策略类型 + 各策略排名

---

### 阶段 2：参数扫描

**目标**：对阶段 1 最优策略进行参数网格搜索。

**扫描维度**：

1. **融合权重**（保守/均衡/积极）：
   - conservative: cp=0.5, gain=0.3, prob=0.2
   - balanced: cp=0.4, gain=0.35, prob=0.25
   - aggressive: cp=0.3, gain=0.4, prob=0.3

2. **持仓天数**：3 / 5 / 7 / 10

3. **止损阈值**：-5% / -8% / -10% / -15%

4. **大盘过滤阈值**：-1% / -2% / -3% / 关闭

**验证方式**：
- 训练集：2024 年数据
- 测试集：2025 年数据（预留）
- 最终评估：2024+2025 全区间

**筛选条件**（必须同时满足）：
- 最大回撤 ≤ 15%
- 年化收益 > 10%
- 交易次数 ≥ 50（样本量足够）

**输出**：最优参数组合 + 训练集/测试集对比

---

### 阶段 3：因子贡献分析

**目标**：量化各因子对收益的边际贡献。

**方法**：逐步剔除法
- 每次剔除一个因子，计算组合收益变化
- 贡献 = 基准收益 - 剔除后收益

**分析因子**：
1. 战力因子（total_cp）
2. 预测涨幅因子（predicted_gain_5d）
3. 上涨概率因子（up_probability_5d）
4. 动量因子（change_pct）
5. 风险因子（risk_penalty）

**输出**：因子贡献排行榜 + 优化建议

---

## 四、实施方案

### 4.1 新增文件

| 文件 | 职责 |
|------|------|
| `backend/backtester/strategy_optimizer.py` | 策略对比 + 参数扫描核心逻辑 |
| `backend/backtester/factor_analyzer.py` | 因子贡献分析 |
| `tests/backtester/test_strategy_optimizer.py` | 单元测试 |

### 4.2 修改文件

| 文件 | 修改内容 |
|------|----------|
| `backend/backtester/strategies.py` | 添加集中持仓参数支持 |
| `backend/backtester/full_backtest.py` | 支持参数化回测 |

### 4.3 API 扩展

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/backtest/optimize` | POST | 触发策略优化流程 |
| `/api/backtest/compare` | GET | 策略对比结果 |
| `/api/backtest/scan` | POST | 参数扫描 |
| `/api/backtest/factor_analysis` | GET | 因子贡献报告 |

---

## 五、测试验证

### 5.1 单元测试

```python
def test_topn_strategy_concentrated():
    # 5-8只持仓，验证选股逻辑

def test_stop_loss_threshold():
    # 止损-10%验证

def test_parameter_scan_grid():
    # 参数组合数量验证
```

### 5.2 集成测试

```bash
# 完整优化流程
python -m pytest tests/backtester/test_strategy_optimizer.py -v

# 2年数据回测（预期运行时间 < 5分钟）
pytest tests/backtester/test_full_backtest.py -k "test_2year" -v
```

---

## 六、预期输出格式

### 策略对比报告

```json
{
  "period": "2024-01-01 to 2025-12-31",
  "strategies": [
    {
      "name": "TopNStrategy",
      "annual_return": 18.5,
      "max_drawdown": 12.3,
      "sharpe": 1.45,
      "calmar": 1.50,
      "win_rate": 62.5,
      "profit_loss_ratio": 1.85,
      "total_trades": 87
    }
  ],
  "best_strategy": "MultiFactorStrategy"
}
```

### 参数扫描报告

```json
{
  "best_params": {
    "fusion_weight": "balanced",
    "max_holding_days": 5,
    "stop_loss": -0.10,
    "market_filter": -0.02
  },
  "train_metrics": { "annual_return": 16.2, "max_drawdown": 11.5 },
  "test_metrics": { "annual_return": 14.8, "max_drawdown": 13.2 },
  "stability_score": 0.91
}
```

### 因子贡献报告

```json
{
  "factors": [
    { "name": "cp_score", "contribution": 0.32, "direction": "positive" },
    { "name": "predicted_gain", "contribution": 0.28, "direction": "positive" },
    { "name": "up_probability", "contribution": 0.15, "direction": "positive" },
    { "name": "momentum", "contribution": 0.08, "direction": "positive" },
    { "name": "risk_penalty", "contribution": -0.02, "direction": "negative" }
  ],
  "recommendation": "增加预测涨幅因子权重，减少风险惩罚权重"
}
```

---

## 七、里程碑

1. **M1**：阶段1完成，6种策略对比报告
2. **M2**：阶段2完成，最优参数组合 + 训练/测试对比
3. **M3**：阶段3完成，因子贡献分析 + 优化建议
4. **M4**：API 集成 + 前端展示优化报告
