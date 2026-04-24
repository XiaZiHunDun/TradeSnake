# ProbabilityPredictor 检查清单

## Auditor 检查项

### 功能正确性
- [ ] features.py 排序字段 trade_date
- [ ] confidence_interval List[float] 类型
- [ ] 计算顺序（先 up_probability 后 interval）
- [ ] data_timestamp 取值逻辑
- [ ] 与 GainPredictor 特征一致性

### 数据流
- [ ] get_klines_bulk 返回类型正确
- [ ] calculate_features 输入格式正确
- [ ] _predict_single 返回格式正确

### 持久化
- [ ] save_to_store 调用正确
- [ ] prediction_store 表结构正确

## Fixer 修复后检查

- [ ] 修复后无语法错误
- [ ] 修复未引人新问题

## Verifier 验证项

- [ ] 代码与文档一致
- [ ] 修复位置正确
- [ ] 无引人新 bug
