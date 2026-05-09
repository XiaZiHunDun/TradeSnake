# Infrastructure 问题追踪

## 记录格式
| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|

状态枚举：待调查 / 已修复 / 保留 / 已验证

---
<!-- 在此下方添加历史问题记录 -->

## 问题追踪

| 日期 | 问题 | 状态 | 修复 |
|------|------|------|------|
| 2026-05-06 | sync_errors_to_issues.py 正则匹配错误：匹配第3列而非第2列 | 已修复 | 修正正则为 `\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^\|]+?)\s*\|` |
| 2026-05-06 | sync_errors_to_issues.py key格式不一致：提取带[]但生成不带[] | 已修复 | 统一去除方括号 |
| 2026-05-06 | sync_errors_to_issues.py 插入位置错误：追加到文件末尾而非section marker前 | 已修复 | 改进插入逻辑，识别section markers |
| 2026-05-06 | sync_errors_to_issues.py 路径映射缺失：backend/tests/test_cp_engine 等未映射到模块 | 已修复 | 添加 backend/tests/ 下所有测试文件的映射 |
