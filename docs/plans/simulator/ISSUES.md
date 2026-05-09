# Simulator 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-23 | can_sell 未实现 T+1 | - | 已修复 | account.py 正确实现 |
| 2026-04-23 | get_market_value 查网络 | - | 已修复 | 使用 SQLite 本地数据 |
| 2026-04-23 | created_at vs recorded_at | - | 已验证修复 | 无字段误用 |
| 2026-05-07 | _execute_limit_sell_fill 未传递 sell_reason | HIGH | 已修复 | orders 表增加 reason 列，create_order/record_trade 传递 reason |
| 2026-05-08 | SIMULATOR_OVERVIEW.md 第225行 trailing_stop=-5% 与版本历史-8% 不一致 | HIGH | 已修复 | 修正为 trailing_stop=-8%，与 Walk-Forward v3 一致 |
| 2026-05-08 | PROJECT_OVERVIEW.md 过户费写"仅沪市"，但2022年后沪深均收 | HIGH | 已修复 | 更新为"沪深均收（2022年后统一）"，与 SIMULATOR_OVERVIEW.md 一致 |
| 2026-05-08 | PROJECT_OVERVIEW.md 初始资金100万 vs SIMULATOR_OVERVIEW.md 2万，差异50倍 | HIGH | 已修复 | 文档注明"simulator默认20000元，API可配置"，明确两处数据的含义 |
| 2026-05-08 | SellAnalyzer 建议止损阈值 -20% vs RiskManager 实盘止损 -7%，差距过大 | HIGH | 已修复 | SellAnalyzer STOP_LOSS_THRESHOLD 从 -0.20 调整为 -0.10，与 RiskManager 的 -7% 止损之间保留合理安全边际 |
| 2026-05-08 | Account 类缺少 peak_assets 属性，导致 check_portfolio_drawdown() 永远比较相同值（current==peak），组合回撤熔断永远不会触发 | HIGH | 已修复 | Account 添加 peak_assets 属性和 update_peak_assets() 方法 |
| 2026-05-08 | simulator RiskControl.MAX_POSITION_RATIO=0.30 与 RiskManager.max_single_position_pct=0.20 不一致 | HIGH | 已修复 | 统一为 20%（v21标准） |

| 限制 | 说明 | 优先级 |
|------|------|--------|
| freeze_shares 空操作 | 从未被调用，不影响 T+1 正确性 | P3 |

## P2 问题（待修复）

暂无
