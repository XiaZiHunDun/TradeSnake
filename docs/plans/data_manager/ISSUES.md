# DataManager 问题记录

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-23 | DuckDB 查询用写连接而非读连接 | - | 已修复 | query() 改用 _get_read_conn() |
| 2026-04-23 | K线返回 DESC 顺序未统一 | - | 已修复 | 统一 ORDER BY trade_date ASC |
| 2026-04-23 | Tushare TOKEN 不一致 | - | 已修复 | - |
| 2026-04-23 | adj_factor 回填未自动执行 | P3 | 已知 limitation | - |

## 已知限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| adj_factor 回填未自动执行 | 需要手动触发 | P3 |
| 四套缓存系统未统一 | fetcher/manager/cache/batcher | P3 |
| BaoStockPool 连接池未真正实现复用 | - | P3 |

## P2 问题（待修复）

暂无
