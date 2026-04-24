# ProbabilityPredictor 问题记录

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-23 | features.py 排序字段用 date 而非 trade_date | - | 已修复 | - |
| 2026-04-23 | 缺少 confidence_interval 字段 | - | 已修复 | - |
| 2026-04-23 | confidence_interval 用未定义变量 | P0 | 已修复 | - |
| 2026-04-23 | 类型不一致 Tuple→List | - | 已修复 | - |
| 2026-04-23 | data_timestamp 取不到值（features 无 date 字段） | - | 已修复 | 改用 klines 获取 trade_date |
| 2026-04-23 | data_timestamp 引用不存在的 prediction.klines 属性 | P0 | 已修复 | 从 klines_dict 获取 |

## 已知限制

无

## P2 问题（待修复）

暂无
