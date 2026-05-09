# TradeSnake 项目约定

## 并行开发

对于可以并行开发的任务，要考虑用 subagent 提高效率。使用 `superpowers:dispatching-parallel-agents` skill 启动多个并行 agent，每个 agent 处理独立任务。

并行任务判断标准：
- 任务之间无数据依赖
- 任务处理不同的模块/文件
- 任务可以同时进行

### Agent Memory 访问规范

**重要**：Agent 无法自动访问 memory 文件。启动 Agent 时必须明确提供 memory 上下文。

**方案一**：在 prompt 中内联关键 memory 内容
```
启动 Agent 时，在 prompt 开头添加：
---
## Memory 上下文
项目概述：股市量化分析系统，v21 策略参数...
模块：cp_engine (WEIGHTS v21: growth=50%, momentum=28%)
---
```

**方案二**：提供 memory 文件完整路径
```
memory 文件位于: ~/.claude/projects/-home-ailearn-projects-TradeSnake/memory/
例如: ~/.claude/projects/-home-ailearn-projects-TradeSnake/memory/cp_engine.md
```

**推荐使用方案一**，因为它更可靠且不需要 Agent 理解路径结构。

## 文档约定

- 核心文档放在 `docs/plans/` 下
- 大文档（>500行）应拆分为 OVERVIEW + DETAIL
- 文档索引页命名：`{MODULE}_ARCHITECTURE.md`

## 错误记录约定

### 发现错误时
1. 记录到对应模块的 `docs/plans/{module}/ISSUES.md`
2. 格式：`日期 | 问题摘要 | 待调查 | -`
3. 包含：失败文件:行号、简要原因
4. CI 测试失败时，`scripts/sync_errors_to_issues.py` 会自动同步

### 问题修复后
1. 更新 ISSUES.md：状态改为"已修复"，在修复列添加修复说明
2. 在 memory/{module}.md 的已知问题记录中添加"已修复"标注
