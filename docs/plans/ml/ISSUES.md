# ML 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->
| 2026-05-06 | [backend/tests/test_ml_model.py] 使用 base 环境导致 lightgbm 找不到 | 保留 | 依赖在 tradesnake conda 环境已安装，CI 应使用正确环境 |
| 2026-05-08 | ml/ARCHITECTURE.md limitations 称"技术因子未验证 IC"但 engine/ARCHITECTURE.md 已验证 macd_diff IC=+0.0185 | HIGH | 已修复 | limitations 第1条更新为"macd_diff IC=+0.0185(t=7.26) 已验证" |

| 指标 | 值 | 说明 |
|------|-----|------|
| Val AUC | 0.506 | 几乎随机，预测能力极弱 |
| Val MAE | 4.23 | 绝对误差偏大 |
| 特征重要性 top-1 | macd_diff (30.8%) | 纯技术因子主导 |
| 训练样本 | 297,408 行 | 数据量充足 |

## Alpha 因子 vs ML 预测对比

Alpha 分析（414 交易日）：
- growth_score IC=+0.0104 (t=2.46 ✅) — 唯一显著 alpha
- momentum IC=+0.009 (t=1.71 ⚠️) — 边界有效
- 技术因子（macd_diff/return_5d）主导 ML 特征重要性，但 IC 未验证

**结论**：ML 模型未能学到 alpha 因子信号，输入特征与 CP 战力体系脱节。

## 待解决问题

| 问题 | 优先级 | 说明 |
|------|--------|------|
| ML 预测能力弱（AUC=0.506） | P0 | 模型几乎随机，无法辅助决策 |
| 特征未使用 CP 战力因子 | P1 | 应将 growth/value/quality/momentum 作为特征输入 |
| walk-forward 训练超时 | P2 | `_get_codes_for_date` fallback 已加 LIMIT 500，仍慢 |
| 特征重要性未验证 IC | P2 | 技术因子 IC 未知，无法判断是否有真实预测力 |

## 建议优化方向

1. **构建技术因子 IC 验证流水线**：在 `alpha_analyzer.py` 中添加 `compute_tech_factor_ic()` 方法
2. **ML 输入加入 CP 因子**：将 `growth_score`, `momentum_score` 等作为特征训练
3. **尝试更长 horizon**：当前 horizon=5，可测试 horizon=10/20
4. **考虑排序学习**：将回归问题改为排序问题（RankingLoss）