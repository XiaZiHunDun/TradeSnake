# Recommender 检查清单

## Auditor 检查项

### 融合逻辑
- [ ] FusionResult.to_dict() 包含 volatility_20d
- [ ] BuySignal._to_dict() 包含 volatility_20d
- [ ] score_breakdown 字段一致性
- [ ] 融合公式 0.4/0.35/0.25

### 仓位计算
- [ ] Kelly 仓位计算
- [ ] 半凯利 Kelly_FRACTION = 0.5

### 过滤条件
- [ ] predicted_gain >= 0
- [ ] up_probability >= 0.5
- [ ] risk_level != 'high'
- [ ] volatility_20d <= 2.52%

## Fixer 修复后检查

- [ ] 修复后无语法错误
- [ ] 修复未引人新问题

## Verifier 验证项

- [ ] 代码与文档一致
- [ ] 修复位置正确
- [ ] 无引人新 bug
