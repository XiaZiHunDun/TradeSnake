# Backtester 检查清单

## Auditor 检查项

### 交易成本
- [x] stamp_tax = 0.0005（不是 0.001）
- [x] 佣金计算正确（0.03%，最低5元）
- [x] 过户费区分沪深市场（沪市双向，深市免）
- [x] 印花税仅卖出收取

### 数据处理
- [x] _fix_change_pct() 修复 change_pct 为 0
- [x] WEIGHTS 不修改全局变量（v21: growth=0.5, momentum=0.28）
- [x] K线数据排序正确（ASC）

### 响应结构
- [x] BacktestTradeResponse.profit 字段存在
- [x] 涨跌停判断 abs(change_pct) < 9.9

### 回测引擎
- [x] FullBacktestEngine vs backtest.py 一致性
- [x] 策略继承和权重配置正确

## Fixer 修复后检查

- [x] 修复后无语法错误（2026-05-07）
- [x] 修复未引入新问题

## Verifier 验证项

- [x] 代码与文档一致
- [x] 修复位置正确
- [x] 无引入新 bug
