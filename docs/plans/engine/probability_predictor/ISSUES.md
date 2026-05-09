# ProbabilityPredictor 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-23 | features.py 排序字段用 date 而非 trade_date | - | 已修复 | - |
| 2026-04-23 | 缺少 confidence_interval 字段 | - | 已修复 | - |
| 2026-04-23 | confidence_interval 用未定义变量 | P0 | 已修复 | - |
| 2026-04-23 | 类型不一致 Tuple→List | - | 已修复 | - |
| 2026-04-23 | data_timestamp 取不到值（features 无 date 字段） | - | 已修复 | 改用 klines 获取 trade_date |
| 2026-05-08 | _apply_limit_adjustment() 涨跌停阈值硬编码 ±9.9%（主板），未使用板块差异化阈值 | MEDIUM | 已修复 | 添加 BOARD_LIMIT_CONFIG，与 gain_predictor 保持一致，支持创业板/科创板/北交所差异化阈值 |
| 2026-05-08 | features.py limit_up/limit_down 特征计算也使用硬编码 ±9.9%，与 predictor.py 不一致 | MEDIUM | 已修复 | features.py 同步添加 BOARD_LIMIT_CONFIG 和 _get_board_type()，使用板块差异化阈值 |

## 已知限制

无

## P2 问题（待修复）

暂无
