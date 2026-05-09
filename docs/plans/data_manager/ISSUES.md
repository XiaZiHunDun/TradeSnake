# DataManager 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-23 | DuckDB 查询用写连接而非读连接 | - | 已修复 | query() 改用 _get_read_conn() |
| 2026-04-23 | K线返回 DESC 顺序未统一 | - | 已修复 | 统一 ORDER BY trade_date ASC |
| 2026-04-23 | Tushare TOKEN 不一致 | - | 已修复 | - |
| 2026-04-23 | adj_factor 回填未自动执行 | P3 | 已知 limitation | - |
| 2026-05-07 | 四套缓存系统未统一 | P3 | 已修复 | DataManager 改用 CacheManager，统一为 HotColdCache |
| 2026-05-07 | fetcher.py get_market_data() 使用 md5_hash 导致缓存失效 | HIGH | 已修复 | 改用简单字符串拼接作为缓存 key |
| 2026-05-07 | state_manager.py 残留错误字符串导致语法错误 | HIGH | 已修复 | 删除错误的 `STATE_DB = str(...)Snake/data")` 行 |
| 2026-05-07 | update_predictions.py predict() 参数类型错误 | HIGH | 已修复 | 先从 DuckDB 获取 K 线数据，再调用 predict(klines_dict) |
| 2026-05-07 | **预测结果未持久化** - predict() 后未调用 save_to_store() | P0 | 已修复 | 添加 gain_pred.save_to_store() 和 prob_pred.save_to_store() |
| 2026-05-08 | DATA_MANAGER_DETAIL.md 观察池更新频率与 stock_selector 不一致 | MEDIUM | 已修复 | 修正为"日频（盘后）"，与 STOCK_SELECTOR_OVERVIEW.md 一致 |
| 2026-05-08 | DATA_LIFECYCLE_DETAIL.md 预测保留期表格180天含义不明确 | MEDIUM | 已修复 | 明确标注"180天（最大上限）"，避免与90天默认保留期混淆 |
| 2026-05-08 | 复权因子未在fetcher.py同步时获取，预测引擎fallback到raw close | MEDIUM | 保留 | 已有解决方案：adjuster.py/filler.py单独获取pro.adj_factor()，duckdb_store.backfill_adj_factor()回填 |
| 2026-05-08 | ml/features.py 使用原价计算技术指标和目标变量，未使用复权价格 | MEDIUM | 待修复 | _build_row 和 build_target 均使用 raw close 而非 adj_close，导致除权缺口影响 IC 验证准确性；建议在特征构建中引入复权逻辑 |

## 已知限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| adj_factor 回填未自动执行 | 需要手动触发 | P3 |
| BaoStockPool 连接池未真正实现复用 | - | P3 |

## P2 问题（待修复）

暂无
