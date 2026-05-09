# Risk 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 |
|------|------|--------|------|
| 2026-05-06 | Kelly计算依赖prediction_store但目前为stub | P2 | 待完善 |
| 2026-05-06 | Walk-Forward参数(TS=-8%)与实盘配置(TS=-5%)不一致 | P2 | **已修复** - constants.py trailing_stop_pct 改为 -0.08 与 walk_forward 一致 |
| 2026-05-07 | Memory记录TS=-5%与代码-0.08不一致 | P2 | **已修复** - 更新MEMORY.md和相关文件与代码统一 |
| 2026-05-07 | test_risk_controller.py 期望 stop_loss=-0.10 但 RiskConfig=-0.07 | HIGH | **已修复** - 测试期望值改为 -0.07 与 v21 标准一致 |
| 2026-05-08 | risk/CHECKLIST.md 第24-25行仍包含已废弃的 TS=-5% 描述 | HIGH | 已修复 | 删除过时描述，与 ARCHITECTURE.md 第60行保持一致（TS=-8%已统一） |
| 2026-05-08 | test_risk_manager.py 尾随止损测试用例 5%drawdown 触发，但 TS=-0.08 需要 8%+ | HIGH | 已修复 | 测试用例改为 9%触发(91/100)、5%不触发(95/100) |
| 2026-05-08 | Kelly两套实现：risk/kelly_calculator.py MAX=50% vs engine/risk_analyzer.py MAX=20% | HIGH | 已修复 | 统一 risk/kelly_calculator.py MAX_POSITION_PCT=20%，与 engine 版本一致 |

## Kelly计算问题

**问题**: `KellyCalculator._get_prediction()` 始终返回 None，Kelly参数使用默认值。

**原因**: 预测系统未提供历史胜率/盈亏比数据。

**解决方向**:
1. 从 `simulator/trade_records` 表计算历史胜率
2. 或从 `prediction_store` 提取预测准确率

## Walk-Forward vs 实盘参数差异

| 参数 | Walk-Forward | 实盘配置 |
|------|--------------|---------|
| Trailing Stop | -8% | -8% ✅（已统一） |
| Stop Loss | -7% | -7% |
| Rebalance | 10天 | 按需 |

> 2026-05-08 修正：实盘 trailing_stop 已统一为 -8%，与 Walk-Forward v3 一致（原文档描述 TS=-5% 有误，已同步修正 risk/ARCHITECTURE.md）。

**注**：表格上方已添加条目记录本次修复。
