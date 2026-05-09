# Risk 模块 Auditor 检查清单

## 每次变更后检查

### RiskManager
- [x] `check_stop_loss()` 亏损计算正确（current/cost - 1）
- [x] `check_trailing_stop()` 返回 RiskCheckResult(should_sell, reason, action)
- [x] `check_portfolio_drawdown()` 组合回撤正确
- [x] `detect_market_regime()` MA20 计算正确
- [x] `calculate_kelly_position_size()` 返回100整数倍

### KellyCalculator
- [x] Kelly公式正确：`(win_rate * (b + 1) - 1) / b`
- [x] 限制上限50%
- [x] half_kelly = kelly * 0.5
- [x] 默认参数合理（win_rate=0.5, avg_win=5%, avg_loss=3%）

### 集成
- [x] `simulator/trader.py` 调用风控检查
- [x] `portfolio.py` 峰值跟踪与风控联动
- [x] 配置文件 `RISK_MANAGEMENT` 与代码一致

### 数值一致性
- [x] Walk-Forward 使用的内联风控参数（TS=-8%）与 RiskManager 默认值一致
- [x] 实盘启用时配置与 Walk-Forward 最优参数一致（TS=-8% 已统一，与 ARCHITECTURE.md 第60行一致）
