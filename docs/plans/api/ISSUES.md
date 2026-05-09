# API 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->
| 2026-05-06 | [backend/tests/test_routes.py] 使用 base 环境导致 FastAPI 找不到 | 保留 | 依赖在 tradesnake conda 环境已安装，CI 应使用正确环境 |
| 2026-05-06 | [backend/tests/test_router_*.py] 同上 | 保留 | 同上 |

## 问题追踪

| 日期 | 问题 | 优先级 | 状态 | 修复说明 |
|------|------|--------|------|----------|
| 2026-04-20 | cp_engine.stocks 并发访问冲突 | P0 | 已修复 | v19.9.3 添加 asyncio.Lock 保护 |
| 2026-04-24 | 收盘后K线填充未触发 | P1 | 已修复 | v19.9.7 修复 last_kline_fill_date 逻辑 |
| 2026-04-25 | 分钟K线填充耗时长阻塞主循环 | P1 | 已修复 | v19.9.8 改为每天50只轮换 |
| 2026-04-26 | adj_factor 回填 DuckDB 失败 | P1 | 已修复 | v19.9.9 修复 backfill_adj_factor 逻辑 |
| 2026-05-08 | API_DETAIL.md 交易端点写 `/api/trade` 单端点，实际是两个端点 `/api/trade/buy` 和 `/api/trade/sell` | HIGH | 已修复 | 文档修正为独立端点，并补充4个遗漏端点 |
| 2026-05-08 | API_OVERVIEW.md 版本号 v18.x 与 API_ARCHITECTURE.md/DETAIL.md v19.9.11 不一致 | MEDIUM | 已修复 | 统一 API 模块版本为 v19.9.11 |
| 2026-05-08 | API_DETAIL.md 端点总表与实际router实现不符 | HIGH | 已修复 | 删除不存在端点（/cp/list, /recommend/buy, /recommend/sell, /swap/suggestions），更正为实际端点（/cp/bottom, /stats/market, /cp/recommend, /cp/swap） |

## 已知限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| CORS 仅支持本地开发环境 | 生产环境需配置真实域名 | P2 |
| 限流器未持久化 | 重启后限流计数清零 | P3 |

## P2 问题（待修复）

暂无
