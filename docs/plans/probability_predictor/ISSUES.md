# Probability Predictor 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-05-08 | confidence_interval_3d/5d 类型声明为 List[float] 但实际使用 Tuple[float, float] | HIGH | 已修复 | `predictor.py` 导入 Tuple 类型并修正类型注解 |
| 2026-05-08 | PROBABILITY_PREDICTOR.md 数据结构未记录 confidence_interval_3d/5d 字段 | MEDIUM | 已修复 | 文档补充两个字段的类型和说明 |

## P2 问题（待修复）

暂无
