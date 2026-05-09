# Frontend 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

## 问题追踪

| ID | 问题 | 优先级 | 状态 |
|----|------|--------|------|
| FE-001 | backtestApi.runSimple 参数未传递给请求 | P0 | ✅ 已修复（2026-04-27） |
| FE-002 | localStorage JSON.parse 缺少异常处理 | P1 | ✅ 已修复（2026-04-27） |

## 已知限制

- 前端工程化不完整：package.json 缺少 lint/test 脚本
- 前端存在遗留 JSX 代码未被 App.tsx 引用
- 前端无障碍（a11y）改进：Header/SearchBar/Backtest 表单缺少 aria 属性

## P2 问题（待修复）

暂无

## 已修复问题

### FE-001: backtestApi.runSimple 参数丢失 (2026-04-27)
**问题**：`params` 被接收但从未使用，后端 `/api/backtest/simple` 需要 `start_date`、`end_date`、`holding_days`、`top_n` 作为 query parameters。
**修复**：将 params 对象序列化为 URLSearchParams 并附加到请求 URL。

### FE-002: localStorage JSON.parse 安全解析 (2026-04-27)
**问题**：`JSON.parse(stored)` 没有 try-catch，如果 stored 损坏会抛出异常。
**修复**：添加 try-catch，解析失败时返回空数组。
