# Risk 模块架构

## 概览

`backend/risk/` — 实盘风控模块，包含 `RiskManager` 和 `KellyCalculator`。

## 核心组件

### RiskManager (`risk_control.py`)

5项风控功能：

| 功能 | 方法 | 说明 |
|------|------|------|
| 固定止损 | `check_stop_loss()` | 亏损达阈值(-7%)强制平仓 |
| 尾随止损 | `check_trailing_stop()` | 从峰值回撤超限(-8%)平仓 |
| 组合回撤熔断 | `check_portfolio_drawdown()` | 组合净值从峰值回撤超限(-15%)减仓/清仓 |
| Kelly仓位 | `calculate_kelly_position_size()` | 按Kelly公式计算建议买入股数 |
| 市场环境识别 | `detect_market_regime()` | 基于MA20判断牛熊，调整仓位上限 |

### KellyCalculator (`kelly_calculator.py`)

Kelly公式：`f* = (p * (b + 1) - 1) / b`

- `kelly_position`: 全Kelly仓位（上限50%）
- `half_kelly`: 半Kelly（更保守）
- `quarter_kelly`: 1/4 Kelly（极度保守）

默认参数：win_rate=0.5, avg_win=5%, avg_loss=3%

## 默认配置（`cp_engine/constants.py`）

```python
RISK_MANAGEMENT = {
    'enabled': True,
    'stop_loss_pct': -0.07,             # 固定止损 -7%
    'trailing_stop_pct': -0.08,          # 尾随止损 -8%（v21 walk_forward 全局最优点）
    'portfolio_drawdown_limit': -0.15,   # 组合回撤 -15%
    'portfolio_drawdown_action': 'reduce',
    'use_kelly_sizing': True,
    'kelly_fraction': 0.5,               # 半Kelly
    'max_single_position_pct': 0.20,     # 单只最大20%
    'market_regime_enabled': True,
    'market_ma_period': 20,
    'bull_position_pct': 1.0,
    'bear_position_pct': 0.5,
}
```

## 集成

- `simulator/trader.py`: 调用 `check_risk_and_execute()` 进行风控检查
- `simulator/portfolio.py`: `update_peak_prices()` 跟踪持仓峰值
- Walk-Forward 回测中为内联逻辑（`walk_forward.py`），不依赖此模块

## 注意事项

- `detect_market_regime()` 需要 DuckDB 中有足够的 K 线数据
- Kelly 计算依赖 `prediction_store`，目前为 stub 实现（返回 None）
- Walk-Forward 回测参数（TS=-8%）与实盘配置一致（均已统一为 TS=-8%）
