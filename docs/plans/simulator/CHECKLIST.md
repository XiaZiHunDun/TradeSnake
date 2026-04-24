# Simulator 检查清单

## Auditor 检查项

### T+1 限制
- [ ] can_sell() T+1 逻辑正确
- [ ] get_holding_batches_for_sell() 排除当日买入

### 持仓管理
- [ ] get_market_value() 从 SQLite 获取
- [ ] 数据库字段 recorded_at（不是 created_at）
- [ ] 冻资冻股逻辑正确

### 风控规则
- [ ] 单股持仓上限 30%
- [ ] 单日买入限额 80%
- [ ] 单日交易次数 10次
- [ ] 最小买卖单位 100股
- [ ] 涨跌停限制

## Fixer 修复后检查

- [ ] 修复后无语法错误
- [ ] 修复未引人新问题

## Verifier 验证项

- [ ] 代码与文档一致
- [ ] 修复位置正确
- [ ] 无引人新 bug
