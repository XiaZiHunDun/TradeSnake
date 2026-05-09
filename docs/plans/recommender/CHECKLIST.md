# Recommender 检查清单

## Auditor 检查项

### 融合逻辑
- [x] FusionResult.to_dict() 包含 volatility_20d
- [x] BuySignal._to_dict() 包含 volatility_20d
- [x] score_breakdown 字段一致性（已拆分为 cp_score/gain_score/prob_score）
- [x] 融合公式 0.4/0.35/0.25（balanced配置，2026-05-07验证）

### 仓位计算
- [x] Kelly 仓位计算（BuyAnalyzer.analyze_buy_opportunity 使用）
- [x] 半凯利 Kelly_FRACTION = 0.5（BuyAnalyzer.STOP_LOSS_PCT = 0.05）

### 过滤条件
- [x] predicted_gain >= 0（PredictionFusion._get_filter_reason 检查）
- [x] up_probability >= 0.5（FILTER_MIN_PROB_5D = 0.5）
- [x] risk_level != 'high'（FILTER_MAX_RISK_LEVEL = 'high'）
- [x] volatility_20d <= 40%（年化，与 probability_predictor 一致）

## Fixer 修复后检查

- [x] 代码正确，CHECKLIST 状态已更新（2026-05-07）

## Verifier 验证项

- [x] 代码与文档一致
- [x] 修复位置正确
- [x] 无引入新 bug
