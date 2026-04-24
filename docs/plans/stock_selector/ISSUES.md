# StockSelector 问题记录

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-23 | on_pool_changed 总是传 PoolTier.CORE | - | 已验证修复 | - |
| 2026-04-23 | load_state 丢失 name 字段 | - | 已验证修复 | - |
| 2026-04-23 | volume_below_threshold_days 未刷新 | - | 已验证修复 | - |
| 2026-04-23 | 晋级未检查 cp_score | - | 已验证修复 | - |
| 2026-04-23 | admission 指数加成逻辑缺陷 | - | 已验证修复 | - |
| 2026-04-23 | volume_below_threshold_days 刷新无效 | - | 已修复 | types.py 添加字段 |
| 2026-04-23 | save_state 未保存白名单/黑名单/观察期记录 | P2 | 已修复 | pool_state_store.py |
| 2026-04-23 | load_state 未恢复白名单/黑名单/观察期记录 | P2 | 已修复 | pool_manager.py |
| 2026-04-23 | on_financial_warning 接口类型不一致 | P2 | 已修复 | 统一为 List[str] |

## 已知限制

无

## P2 问题（待修复）

暂无
