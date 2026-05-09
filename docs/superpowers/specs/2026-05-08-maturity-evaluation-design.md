# 策略成熟度评估体系设计方案

> **日期**: 2026-05-08
> **目标**: 建立像模型训练收敛一样的策略"停止训练"标准

## Context

目前项目没有统一的策略成熟度评估机制。策略优化会无限进行下去，无法判断"何时足够好"。需要建立双层标准体系：长期毕业标准和短期每日信号。

---

## 一、双层标准体系

### 1.1 毕业标准（长期 - "停止优化"触发器）

**触发条件（需同时满足）：**

| 指标 | 阈值 | 说明 |
|------|------|------|
| 滚动月盈利 | ≥5/6 个月盈利 | 每月收益 >0.5%（跑赢无风险利率） |
| 基准超额 | 相对沪深300超额 >0% | 跑赢大盘才算真能力 |
| IS/OOS差距 | OOS Sharpe / IS Sharpe > 0.8 | 防过拟合，差距 <20% |

**触发结果：**
- 策略标记为"成熟"(mature)，可 autonomous 运行
- 每日信号全档位开放（强烈买入/观望/空仓）

### 1.2 每日信号（短期 - 交易决策参考）

**三档信号：**

| 档位 | 信号 | 触发条件 | 毕业前 | 毕业后 |
|------|------|----------|--------|--------|
| 🟢 | 强烈买入 | Kelly仓位 > 8% + 风险低 + 预测向上 | ✅ 可执行 | ✅ 可执行 |
| 🟡 | 观望 | 中等机会，等待更明确信号 | ❌ 禁止 | ✅ 可执行 |
| 🔴 | 空仓 | 风险过高 / 策略未达毕业标准 | ✅ 强制 | ✅ 可执行 |

---

## 二、毕业标准详解

### 2.1 滚动月盈利计算

```
统计周期：过去 6 个月
盈利定义：月末持仓市值 - 月初持仓市值 > 月初市值 × 0.5%
达标条件：≥5 个月满足定义
```

**数据来源：**
- 实盘数据：simulator 持仓记录，按月统计
- 模拟盘：用 backtester 的完整回测结果，按月切分

### 2.2 基准超额计算

```
超额收益 = 策略月度收益 - 沪深300同期涨幅
统计周期：过去 6 个月
达标条件：6个月平均超额 > 0%
```

**数据来源：**
- 沪深300日线数据（data_manager 提供）
- 月度收益对比

### 2.3 IS/OOS 过拟合检验

```
方法：Walk-Forward 滚动验证
IS Sharpe：训练窗口内 Sharpe
OOS Sharpe：测试窗口内 Sharpe
达标条件：OOS/IS > 0.8（即 OOS 性能达到 IS 的 80% 以上）
```

**说明：**
- Walk-Forward v3 已实现此功能（Annual 13.89%, Sharpe 0.50）
- 需在毕业前重新跑完整验证，确保参数未过拟合

---

## 三、每日信号生成规则

### 3.1 Kelly 仓位计算

```python
# 来自 BuyAnalyzer
kelly_position = KellyCalculator.get_position_recommendation(
    win_rate, win_loss_ratio, total_capital, risk_preference
).recommended_position_pct
```

### 3.2 风险评估

| 风险等级 | 触发条件 | 档位 |
|----------|----------|------|
| 低 (acceptable) | risk_score < 50, volatility_20d < 30 | 🟢 强烈买入 |
| 中 (warning) | risk_score 50-70 或 volatility 30-40 | 🟡 观望 |
| 高 (high) | risk_score > 70 或 volatility > 40 | 🔴 空仓 |

### 3.3 预测信号

| 预测方向 | 触发条件 | 档位 |
|----------|----------|------|
| 向上 | predicted_gain_5d > 5% AND up_probability_5d > 0.6 | 🟢 强烈买入 |
| 中性 | predicted_gain_5d 0-5% OR up_probability_5d 0.5-0.6 | 🟡 观望 |
| 向下 | predicted_gain_5d < 0 OR up_probability_5d < 0.5 | 🔴 空仓 |

### 3.4 综合信号输出

```python
def generate_daily_signal(
    kelly_position: float,
    risk_level: str,        # acceptable/warning/high
    predicted_gain_5d: float,
    up_probability_5d: float,
    is_mature: bool         # 是否达到毕业标准
) -> str:  # "strong_buy" / "watch" / "empty"

    # 毕业前只允许强烈买入
    if not is_mature and kelly_position > 8:
        return "strong_buy"  # 🟢
    elif not is_mature:
        return "empty"  # 🔴 毕业前非强烈买入都禁止

    # 毕业后按综合判断
    if kelly_position > 8 and risk_level == 'acceptable' and up_probability_5d > 0.6:
        return "strong_buy"  # 🟢
    elif risk_level == 'high' or up_probability_5d < 0.5:
        return "empty"  # 🔴
    else:
        return "watch"  # 🟡
```

---

## 四、实现计划

### 4.1 新增模块

```
backend/maturity/
├── __init__.py
├── evaluator.py      # 毕业标准评估器
├── daily_signal.py  # 每日信号生成器
└── metrics.py      # 指标计算（滚动盈利、基准超额等）
```

### 4.2 依赖关系

```
simulator/trader.py → maturity/daily_signal.py → 输出每日档位
backtester/walk_forward.py → maturity/evaluator.py → 输出是否毕业
recommender → maturity/daily_signal.py → 获取当前档位
```

### 4.3 API 端点

| 端点 | 方法 | 输出 | 说明 |
|------|------|------|------|
| `/api/maturity/status` | GET | 毕业状态 + 各项指标 | 是否达到毕业标准 |
| `/api/maturity/daily_signal` | GET | 今日档位 + 详情 | 每日交易信号 |
| `/api/maturity/history` | GET | 历史月度表现 | 滚动盈利追踪 |

---

## 五、毕业后的行为变化

| 场景 | 毕业前 | 毕业后 |
|------|--------|--------|
| Kelly 8%，风险低，预测向上 | 🟢 强烈买入 | 🟢 强烈买入 |
| Kelly 5%，风险中，预测中性 | 🔴 空仓 | 🟡 观望（可操作） |
| Kelly 15%，风险高 | 🔴 空仓 | 🔴 空仓（强制） |
| 策略是否自动运行 | 需人工确认 | 可 autonomous |

---

## 六、持续监控

即使达到毕业标准，也需要持续监控：

| 监控项 | 频率 | 阈值 | 触发动作 |
|--------|------|------|----------|
| 月度盈利连续性 | 每月 | 连续2个月亏损 | 警告，降级为未毕业 |
| IS/OOS 比率 | 每季 | OOS/IS < 0.7 | 重新优化参数 |
| 基准超额 | 每季 | 连续2季度跑输大盘 | 警告，复查策略 |

---

## 七、验证方法

1. **回测验证**：用历史数据模拟评估器，看是否正确识别"成熟"状态
2. **每日信号回测**：对历史信号做回测，验证"强烈买入"档位的盈利能力
3. **虚盘测试**：达到毕业标准后，先用 simulator 虚盘验证3个月再实盘

---

## 八、总结

**核心原则：**
1. 回测赚钱 ≠ 实盘赚钱，毕业标准防过拟合
2. 每日信号分档控制风险，毕业前只执行高确信度交易
3. 毕业后仍持续监控，不盲目信任

**毕业触发条件（简版）：**
- 滚动6个月 ≥5个月盈利（>0.5%）
- 相对沪深300超额 >0%
- OOS/IS Sharpe > 0.8