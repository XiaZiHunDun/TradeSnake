# Backtester 检查清单

## Auditor 检查项

### 交易成本
- [ ] stamp_tax = 0.0005（不是 0.001）
- [ ] 佣金计算正确（0.03%，最低5元）
- [ ] 过户费区分沪深市场
- [ ] 印花税仅卖出收取

### 数据处理
- [ ] _fix_change_pct() 修复 change_pct 为 0
- [ ] WEIGHTS 不修改全局变量
- [ ] K线数据排序正确（ASC）

### 响应结构
- [ ] BacktestTradeResponse.profit 字段存在
- [ ] 涨跌停判断 abs(change_pct) < 9.9

### 回测引擎
- [ ] FullBacktestEngine vs backtest.py 一致性
- [ ] 策略继承和权重配置正确

## Fixer 修复后检查

- [ ] 修复后无语法错误
- [ ] 修复未引人新问题

## Verifier 验证项

- [ ] 代码与文档一致
- [ ] 修复位置正确
- [ ] 无引人新 bug
