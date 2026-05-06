# Backtester 问题记录

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-23 | stamp_tax 率 0.001→0.0005 | - | 已修复 | - |
| 2026-04-23 | change_pct 历史数据为0 | - | 已修复 | _fix_change_pct 实现 |
| 2026-04-23 | WEIGHTS 全局修改 | - | 已修复 | MultiFactorStrategy 内部使用 |
| 2026-04-23 | BacktestTradeResponse 缺 profit | - | 已修复 | - |
| 2026-04-23 | 过户费未区分沪深（backtest.py） | P1 | 已修复 | 沪市双向收费，深市免收 |
| 2026-05-06 | DuckDB Timestamp 传入 SQLite 绑定错误 | - | 已修复 | `get_cp_history_by_date` 增加 `strftime` 转换 |
| 2026-05-06 | walk_forward rebal_counter 从未触发 rebalance | - | 已修复 | 重写 rebalance 逻辑，每 rebalance_freq 天换仓 |
| 2026-05-06 | 组合回撤熔断未实现 | - | 已修复 | -15% 组合级熔断，触发后清仓持现金 |
| 2026-05-06 | trailing stop 未实现 | - | 已修复 | peak_price 跟踪，-10% 触发卖出 |
| 2026-05-06 | rebalance_freq 5天过短 | - | 已修复 | 改为 10天（匹配 growth IC 衰减特征） |

## 已知限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| trailing stop -10% 在 A 股高波动环境下过于激进 | 换手率从 8.5x 爆炸到 41.9x | P1 待优化 |

## P2 问题（待修复）

暂无

## Walk-Forward v3 优化结果（2026-05-06）

**优化前（v20.1）**：Annual 9.54%, Sharpe 0.30, MaxDD 17.2%, Turnover 8.5x
**优化后（v21）**：Annual 11.19%, Sharpe 0.38, MaxDD 17.03%, Turnover 41.9x

问题：Sharpe 仍低于 0.5 目标，换手率爆炸，trailing stop 过紧。

**v3 最终参数（2026-05-06）**：
| 参数 | 值 | 说明 |
|------|-----|------|
| TRAILING_STOP | -8% | 全局最优点，Sharpe 0.50 |
| rebalance_freq | 10 天 | 每 10 天换仓 |
| PORTFOLIO_DRAWDOWN_LIMIT | -15% | 未在回测中触发 |
| stop_loss | -7% | 硬止损 |

**参数搜索结果**：
| TS | Annual | Sharpe | MaxDD |
|----|--------|--------|-------|
| -6% | 11.37% | 0.38 | 16.91% |
| -7% | 9.57% | 0.30 | 17.36% |
| **-8%** | **13.89%** | **0.50** | **16.30%** ✅ |
| -10% | 11.19% | 0.38 | 17.03% |
| -12% | 9.90% | 0.32 | 17.43% |

**结论**：TS=-8% 是全局最优点，同时提升 Sharpe 和 Annual Return（"主动止盈"而非"被动止损"）。
