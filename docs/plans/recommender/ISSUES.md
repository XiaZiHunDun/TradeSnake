# Recommender 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-23 | volatility_20d 在 to_dict 输出丢失 | - | 已修复 | - |
| 2026-04-23 | score_breakdown 与 FusionResult 不匹配 | - | 已修复 | - |
| 2026-04-27 | FILTER_MAX_VOLATILITY 单位错误（除以 sqrt(252) 导致年化 % 与日度 % 混淆） | P1 | 已修复 | `fusion.py` FILTER_MAX_VOLATILITY 改为 40（年化 %） |
| 2026-05-08 | BuyAnalyzer STOP_LOSS_PCT=0.05 与 v21 风控标准(-7%)不一致 | HIGH | 已修复 | `buy_analyzer.py` STOP_LOSS_PCT 改为 0.07 与 v21 风控标准一致；`RECOMMENDER_OVERVIEW.md` 同步更新 |
| 2026-05-08 | confidence_interval_3d/5d 类型声明为 List[float] 但实际使用 Tuple[float, float] | HIGH | 已修复 | `predictor.py` 导入 Tuple 类型并修正类型注解；`PROBABILITY_PREDICTOR.md` 补充字段文档 |
| 2026-05-08 | RECOMMENDER_OVERVIEW.md BuySignal stop_loss 注释为 -5% 但代码已为 -7% | HIGH | 已修复 | 文档注释修正为 -7%（v21风控标准） |
| 2026-05-08 | buy_analyzer.py BuySignal dataclass docstring 和 prompt 模板仍写 -5%，但代码已是 -7% | HIGH | 已修复 | 代码注释全部更新为 -7%（v21风控标准） |
| 2026-05-08 | BuyAnalyzer.get_buy_signals() 接收 risk_preference 参数但未传递给 Kelly 计算，导致 conservative 模式不生效 | MEDIUM | 已修复 | `analyze_buy_opportunity()` 添加 `risk_preference` 参数，使用 `get_position_recommendation()` 代替 `calculate_kelly_fraction()` |
| 2026-05-08 | **P1: board_type 命名不一致** - filters.py 使用 `gem`/`bge`，gain_predictor 使用 `chinext`/`bj`，cp_engine 使用 `gem`/`bge`。阈值 9.9% vs 10% 也有差异 | HIGH | 待修复 | 建议统一使用 `gem`/`star`/`bge`/`main`（cp_engine 命名），更新 gain_predictor/probability_predictor 的 BOARD_LIMIT_CONFIG |
| 2026-05-08 | **P1: 前端 API 路径缺少 /api 前缀** - verifyApi/healthApi/userApi 调用 `/verify/*`、`/health`、`/user/profile` 而非 `/api/*` | HIGH | 已修复 | api.ts 已有 API_BASE='/api'，但实际调用时路径正确，agent 误报 |

## 已知限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| fusion 公式文档缺少 confidence multiplier 说明 | - | P3 |

## P2 问题（待修复）

暂无
