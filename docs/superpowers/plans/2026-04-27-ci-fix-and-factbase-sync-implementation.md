# 任务：CI 修复 + 事实文档同步 + README 更新

> 日期：2026-04-27  
> 类型：Infrastructure + Documentation（低风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：`2026-04-27-config-frontend-tests-implementation.md`（已完成）

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

---

## Goal

三个小型修复，一次性完成：

1. 修复 `.github/workflows/ci.yml` 的 YAML 缩进错误，使 GitHub Actions 能正确解析
2. 更新 `PROJECT_FACT_BASE.md`，反映最新完成的 config/frontend/tests 任务成果
3. 同步根目录 `README.md`，移除过时描述

完成后：CI 可以正确运行、事实文档准确反映项目现状、README 不再误导。

---

## Context

### 已知问题 1：CI YAML 缩进

`.github/workflows/ci.yml` 第 23 行 `- name: Run backend tests` 缺少前导空格，与第 19 行 `- name: Install dependencies` 的缩进不一致。GitHub Actions YAML 解析会失败。

正确缩进应为 6 个空格（与同层其他 step 对齐）。

### 已知问题 2：PROJECT_FACT_BASE 过时

以下内容已过时需更新：

- §2.2 前端：仍提到 ECharts、xlsx（已被移除）
- §5.5 前端工程化：仍说"只有 dev、build、preview"（现已有 lint、format、typecheck、test）
- §5.4 测试范围：基线数据需更新为 250 passed + 25 route tests + 48 backtester
- 缺少 §关于 `backend/config.py` 的记录
- §6.3 前端命令：仍说"不应假设 lint/test 可用"

### 已知问题 3：README 过时

- 目录结构仍显示 `core/`（已不存在）
- 仍提到 ECharts
- 启动命令可能仍用旧格式

---

## Scope

Allowed changes:

- `.github/workflows/ci.yml`
- `docs/superpowers/plans/PROJECT_FACT_BASE.md`
- `README.md`（根目录）

Out of scope:

- 任何 `backend/` 或 `frontend/` 代码文件
- 任何其他文档（除非上述三文件引用了需要修正的路径）
- `backend/api/router.py`（用户可能有未提交改动）

---

## Autonomy

Claude Code 可以自主决定：

- README 中过时内容的删除或替换措辞
- PROJECT_FACT_BASE 中事实更新的表述方式
- CI YAML 中格式对齐的空格数量（只要语义正确）

---

## Stop Conditions

- 发现 CI YAML 的问题不是简单缩进，而是逻辑错误需要重新设计 workflow
- 发现 README 改动会影响用户已有的部署脚本或自动化
- 需要运行 CI 来验证但无法本地模拟

---

## Steps

### Part 1：修复 CI YAML

- [ ] 读取 `.github/workflows/ci.yml`
- [ ] 修复第 23 行 `- name: Run backend tests` 的缩进，对齐到与其他 steps 相同的层级（6 空格前缀）
- [ ] 同时检查：前端 job 是否应该添加 `npm run lint` 和 `npm run typecheck`（不再用 `|| true`）
- [ ] 更新前端 job：
  - 将 `npx tsc --noEmit || true` 改为 `npm run typecheck`（现在 typecheck 能通过了）
  - 添加 `npm run lint` step（现在 lint 能通过了）
- [ ] 确保 YAML 语法正确（可用 `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` 验证）

### Part 2：更新 PROJECT_FACT_BASE

- [ ] 读取当前 `docs/superpowers/plans/PROJECT_FACT_BASE.md`
- [ ] 更新 §2.2 前端技术栈：
  - 删除 ECharts、xlsx
  - 添加 ESLint、Prettier、Vitest
  - 更新 scripts 列表为 dev/build/preview/lint/format/typecheck/test/test:watch
- [ ] 更新 §5.4 测试范围：
  - 基线更新为：backend/tests/ 250 passed, test_routes 25 passed (7 integration deselected), tests/backtester/ 48 passed
  - 添加 `pyproject.toml` 已创建（pythonpath + markers + testpaths）
- [ ] 更新 §5.5 前端工程化：
  - 标记为 ✅ 已修复，说明 ESLint + Prettier + Vitest 已配置
  - 保留"0 个前端测试文件"作为待改进项
- [ ] 新增一条关于 `backend/config.py` 的事实（§2.1 或新的 §）：
  - 所有文件系统路径集中在 `backend/config.py`
  - 支持 `TRADESNAKE_DATA_DIR` 环境变量覆盖
  - 15+ 文件已迁移为 `from backend.config import ...`
- [ ] 更新 §6.3 前端命令，反映 lint/typecheck/test 现在可用
- [ ] 更新日期为 2026-04-27

### Part 3：更新 README

- [ ] 读取根目录 `README.md`
- [ ] 修复目录结构：删除 `core/` 相关描述
- [ ] 删除 ECharts/xlsx 相关提及
- [ ] 确认启动命令格式为 `python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001`
- [ ] 如有 `npm run lint` 相关旧描述，更新为当前可用命令
- [ ] 保持 README 简洁，不做大规模重写

---

## Verification

```bash
# Part 1: CI YAML 语法验证
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"

# Part 2: 事实文档无占位符
rg 'TODO|TBD|PLACEHOLDER|待补充' docs/superpowers/plans/PROJECT_FACT_BASE.md

# Part 3: README 无过时引用
rg 'core/' README.md
rg 'echarts' README.md -i
rg 'cd backend' README.md

# 综合：确认文件存在且非空
test -s .github/workflows/ci.yml && echo "ci.yml OK"
test -s docs/superpowers/plans/PROJECT_FACT_BASE.md && echo "fact_base OK"
test -s README.md && echo "readme OK"
```

---

## Completion Report Format

```markdown
## Summary
- 按 Part 列出所有修改

## Verification
- 每项验证命令的输出

## Files Modified
- 列表

## Remaining Issues
- 未修复的问题

## Next Task Recommendation
- 后续建议
```
