# Backtester 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

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
| 2026-05-07 | walk_forward.py 缺少滑点计算 | MEDIUM | 已修复 | 添加 SLIPPAGE_RATE=0.1%，计入 buy_cost_rate 和 sell_cost_rate |
| 2026-05-07 | MultiFactorStrategy 默认权重与 v21 不一致 | MEDIUM | 已修复 | 改为 growth=0.50, value=0.00, momentum=0.28, quality=0.05 |
| 2026-05-07 | cost_model.py 佣金率万1，应为万3 | HIGH | 已修复 | COMMISSION_RATE 0.0001→0.0003 |
| 2026-05-07 | BacktestResult.to_dict() 引用未定义字段 avg_holding_days | CRITICAL | 已修复 | 在 BacktestResult dataclass 添加 avg_holding_days: float = 0 字段 |
| 2026-05-07 | walk_forward trailing_stop -8% 与 constants trailing_stop_pct -5% 不一致 | 冲突 | 已修复 | constants.py trailing_stop_pct 改为 -0.08 |
| 2026-05-07 | backtester/risk_controller.py 的 RiskController 从未被调用（死代码） | MEDIUM | **已删除** | 风控逻辑已整合到 FullBacktestEngine，RiskManager负责实盘 |
| 2026-05-07 | simulator trades 表缺失 CREATE TABLE 定义 | CRITICAL | 已修复 | 在 _create_tables() 中添加 trades 表定义 |
| 2026-05-07 | simulator trades 表缺失 sell_reason 字段 | HIGH | 已修复 | 添加 sell_reason 列并在 record_trade() 中写入 |
| 2026-05-07 | _execute_limit_sell_fill 未传递 sell_reason | HIGH | 已修复 | orders 表增加 reason 列，create_order/record_trade 传递 reason |
| 2026-05-07 | test_risk_controller.py 期望 stop_loss=-0.10 但 RiskConfig=-0.07 | HIGH | 已修复 | 测试期望值改为 -0.07 与 v21 标准一致 |

## 已知限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| trailing stop -8% 换手率仍较高（42x） | 相比 v20.1 的 8.5x 增长明显，但符合主动止盈策略 | P2 观察 |

## P2 问题（待修复）

暂无

## Walk-Forward v3 优化结果（2026-05-06）

**优化前（v20.1）**：Annual 9.54%, Sharpe 0.30, MaxDD 17.2%, Turnover 8.5x
**v21 最终**：Annual 13.89%, Sharpe 0.50, MaxDD 16.30%, Turnover 42x

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
