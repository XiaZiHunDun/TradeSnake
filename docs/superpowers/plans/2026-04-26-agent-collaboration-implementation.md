# Agent 协作体系实施任务

> **For Claude Code:** REQUIRED PROCESS: Execute this task continuously. Do not ask the user about routine engineering or documentation choices. Stop only when a stop condition below is met.  
> **Goal:** 核对并完善 TradeSnake 的 agent 协作基础文件，让后续 Cursor 代理可以持续产出任务，Claude Code 可以按任务文件连续执行。

---

## 一、任务背景

本任务用于建立 TradeSnake 的“Cursor 负责分析/设计/评审，Claude Code 负责执行”的基础工作流。

已创建的基础文件：

- `docs/superpowers/specs/2026-04-26-agent-collaboration-design.md`
- `docs/superpowers/plans/CLAUDE_CODE_TASK_TEMPLATE.md`
- `docs/superpowers/plans/PROJECT_FACT_BASE.md`
- `docs/superpowers/plans/2026-04-26-agent-collaboration-implementation.md`

相关既有事实源：

- `README.md`
- `docs/README.md`
- `docs/plans/PROJECT_OVERVIEW.md`
- `.github/workflows/ci.yml`
- `backend/requirements.txt`
- `frontend/package.json`
- `backend/api/main.py`
- `frontend/src/App.tsx`
- `frontend/src/shared/services/api.ts`

---

## 二、执行原则

Claude Code 应自主推进：

- 文档措辞、结构和路径索引的常规修正。
- 与事实基线一致的小范围补充。
- 缺失但明显必要的文档链接。
- 文档检查命令与结果记录。

Claude Code 不应自主做：

- 修改业务代码。
- 修改产品范围、战力公式、交易费用、回测标准或数据源优先级。
- 删除或重写历史文档。
- 修改 `.claude/settings.local.json` 权限。
- 提交 git commit，除非用户单独要求。

必须停下询问用户：

- 发现基础文件中的协作规则会授权 Claude Code 改变产品策略。
- 需要选择新的目录体系而不是继续使用 `docs/superpowers`。
- 需要修改用户已有未提交代码才能完成任务。
- 文档验证发现严重冲突，无法在不改变设计意图的情况下修复。

---

## 三、允许修改范围

允许创建或修改：

- `docs/superpowers/specs/2026-04-26-agent-collaboration-design.md`
- `docs/superpowers/plans/CLAUDE_CODE_TASK_TEMPLATE.md`
- `docs/superpowers/plans/PROJECT_FACT_BASE.md`
- `docs/superpowers/plans/2026-04-26-agent-collaboration-implementation.md`
- `docs/README.md`，仅允许增加 `docs/superpowers` 的索引说明。

禁止修改：

- `backend/`
- `frontend/`
- `data/`
- `.claude/settings.local.json`
- 用户已有未提交改动文件，例如 `backend/api/router.py`

---

## 四、执行步骤

### Task 1: Read And Protect Worktree

- [ ] Run `git status --short --branch`.
- [ ] Identify existing user changes.
- [ ] Confirm no protected file needs modification.

Expected current known condition:

- `backend/api/router.py` may already be modified before this task starts.
- Do not touch it.

### Task 2: Review Collaboration Design

- [ ] Read `docs/superpowers/specs/2026-04-26-agent-collaboration-design.md`.
- [ ] Confirm it clearly separates user, Cursor agent, and Claude Code responsibilities.
- [ ] Confirm it encourages autonomous execution for routine choices.
- [ ] Confirm stop conditions protect product scope, data policy, persistence, API compatibility, credentials, and destructive git actions.
- [ ] Fix wording if any rule is ambiguous or over-authorizes execution.

### Task 3: Review Task Template

- [ ] Read `docs/superpowers/plans/CLAUDE_CODE_TASK_TEMPLATE.md`.
- [ ] Confirm every future task has Goal, Context, Scope, Autonomy, Stop Conditions, Files, Steps, Verification, and Report.
- [ ] Confirm the template tells Claude Code not to ask about routine details.
- [ ] Confirm verification examples match this repository.
- [ ] Fix wording or examples if they could mislead future execution.

### Task 4: Review Project Fact Base

- [ ] Read `docs/superpowers/plans/PROJECT_FACT_BASE.md`.
- [ ] Cross-check the stated facts against key files listed in section 一.
- [ ] Confirm known conflicts are recorded: README v18 vs overview v19.9.9, backend import path, CI dependency mismatch, test scope mismatch, frontend engineering gaps.
- [ ] Fix factual inaccuracies with direct evidence from the current repository.

### Task 5: Link Superpowers Docs From Docs Index

- [ ] Read `docs/README.md`.
- [ ] If `docs/superpowers` is not mentioned, add a concise index entry explaining:
  - `docs/superpowers/specs` stores Cursor design documents.
  - `docs/superpowers/plans` stores Claude Code execution tasks and templates.
- [ ] Keep the change small and avoid reorganizing the whole docs index.

### Task 6: Documentation Verification

- [ ] Run a search ensuring new docs do not contain placeholder markers:

```bash
rg -n "TO""DO|TB""D|PLACE""HOLDER|待补""充" docs/superpowers/specs/2026-04-26-agent-collaboration-design.md docs/superpowers/plans/CLAUDE_CODE_TASK_TEMPLATE.md docs/superpowers/plans/PROJECT_FACT_BASE.md docs/superpowers/plans/2026-04-26-agent-collaboration-implementation.md
```

- [ ] Run a file existence check:

```bash
test -f docs/superpowers/specs/2026-04-26-agent-collaboration-design.md && \
test -f docs/superpowers/plans/CLAUDE_CODE_TASK_TEMPLATE.md && \
test -f docs/superpowers/plans/PROJECT_FACT_BASE.md && \
test -f docs/superpowers/plans/2026-04-26-agent-collaboration-implementation.md
```

- [ ] Run `git diff -- docs/superpowers docs/README.md` and review the final diff.

### Task 7: Report

- [ ] Summarize the final files changed.
- [ ] Include verification commands and results.
- [ ] List any existing repo issues observed but not fixed.
- [ ] Recommend the next concrete execution task.

---

## 五、完成汇报格式

Use this exact structure:

```markdown
## Summary
- State the collaboration docs created or refined.

## Verification
- `<command>`: result.

## Existing Issues Or Risks
- List known repo conflicts or risks not fixed by this task.

## Next Task Recommendation
- Recommend one concrete next task.
```

---

## 六、推荐下一任务

完成本任务后，建议下一项交给 Claude Code 的执行任务是：

统一后端启动命令、README 与 CI 的导入路径，先通过实际命令验证 `backend.api.main:app` 与 `api.main:app` 的可用性，再做最小文档或 CI 修正。
