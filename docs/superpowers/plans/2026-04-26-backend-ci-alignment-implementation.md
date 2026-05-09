# 后端启动命令统一与依赖对齐

> **For Claude Code:** Execute this task continuously. Make routine engineering decisions yourself. Stop only when a stop condition is met.  
> **Fact base:** Read `docs/superpowers/plans/PROJECT_FACT_BASE.md` first.  
> **Template:** This task follows `docs/superpowers/plans/CLAUDE_CODE_TASK_TEMPLATE.md`.

---

## Goal

使 `backend/requirements.txt`、`.github/workflows/ci.yml` 和 `README.md` 中的后端依赖与启动命令互相一致，并修复 CI 中 `api-health-check` job 缺少 `actions/checkout` 的问题。

验收标准：

- `backend/requirements.txt` 包含当前代码直接导入的所有第三方包。
- `.github/workflows/ci.yml` 的 `backend-test` job 从 `requirements.txt` 安装依赖，而不是手动列包。
- `.github/workflows/ci.yml` 的 `api-health-check` job 有 `actions/checkout` 步骤。
- `README.md` 中后端启动命令与代码实际可用方式一致。
- 现有 `python -m pytest backend/tests/ -v` 仍能通过。

---

## Context

### 导入路径现状

后端代码几乎全部使用 `from backend.xxx` 导入（跨模块超过 140 处）。这意味着 Python 运行时需要把仓库根目录加入 `sys.path`。

当前两种启动方式：

- README 写法：`cd backend && python -m uvicorn api.main:app --reload --port 8001`。这依赖 `backend/tests` 里的 `sys.path.insert` hack，以及 `api.main` 模块内不直接在顶层触发 `from backend.xxx`（实际会失败，因为 `main.py` 第 18 行就是 `from backend.api.router import ...`）。
- 实际可用写法：从仓库根目录运行 `python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001`。

CI 的 `api-health-check` 用 `cd backend && from api.main import app`，但同时缺少 `actions/checkout`。

结论：应以仓库根目录 + `backend.api.main:app` 为标准启动方式。

### 依赖现状

`backend/requirements.txt` 当前内容：

```
fastapi==0.115.0
uvicorn==0.30.0
akshare==1.18.49
pandas==2.2.0
requests==2.32.0
pydantic==2.8.0
sqlalchemy==2.0.0
aiosqlite==0.20.0
```

代码中实际导入但 requirements.txt 缺失的包：

| 包 | 使用位置 |
|----|----------|
| slowapi | `backend/api/main.py` |
| numpy | `backend/engine/cp_engine/cp_engine.py`, `backend/backtester/` 多文件 |
| scipy | `backend/backtester/factor_attributor.py`, `backend/api/router.py` |
| baostock | `backend/data_manager/fetcher.py` |
| duckdb | `backend/data_manager/duckdb_store.py` |

CI 的 `pip install` 也是手动列包，与 requirements.txt 不同步。

---

## Scope

允许修改：

- `backend/requirements.txt` - 补齐缺失依赖
- `.github/workflows/ci.yml` - 修复依赖安装和 checkout 问题
- `README.md` - 更新后端启动命令段落（仅"运行 > 后端"部分）
- `docs/superpowers/plans/PROJECT_FACT_BASE.md` - 更新已知冲突状态

禁止修改：

- `backend/` 下的 Python 源码 - 不改业务代码
- `frontend/` - 不在本任务范围
- `backend/api/router.py` - 有用户未提交改动
- `.claude/settings.local.json`

---

## Autonomy

Claude Code 可自主决定：

- 补齐依赖时使用的具体版本号（优先使用当前环境已安装的版本，用 `pip show <pkg>` 查询）。
- CI YAML 中 `pip install -r requirements.txt` 后是否追加 `pytest`（因为 pytest 是测试工具不是运行时依赖，可以单独列）。
- README 启动命令的具体措辞，只要保持准确。
- 是否在 CI 中用 `pip install -r` 替代手动列包。

Claude Code 应优先选择：

- 最小改动。
- 不引入新的不一致。
- 可通过验证的方案。

---

## Stop Conditions

遇到以下情况必须停下询问用户：

- 发现某个依赖包在当前环境中不存在且无法确定版本。
- 发现修改 CI 会导致当前 CI 流水线更大范围的变化。
- 发现 README 启动命令需要改变 conda 环境配置。
- 发现 `backend/api/router.py` 需要修改才能让启动方式生效。
- 现有测试 `python -m pytest backend/tests/ -v` 大面积失败且与本次改动无关。

---

## Files

Modify:

- `backend/requirements.txt` - 补齐 slowapi, numpy, scipy, baostock, duckdb
- `.github/workflows/ci.yml` - 使用 requirements.txt 安装; 修复 api-health-check 缺少 checkout; 统一启动命令
- `README.md` - 更新"运行 > 后端"段落
- `docs/superpowers/plans/PROJECT_FACT_BASE.md` - 标记 5.2 和 5.3 为已修复或进展

Do not modify:

- `backend/` 下任何 `.py` 文件
- `frontend/` 目录
- `backend/api/router.py` - 用户已有改动

---

## Steps

### Task 1: Prepare

- [ ] Read `docs/superpowers/plans/PROJECT_FACT_BASE.md`.
- [ ] Run `git status --short` and confirm `backend/api/router.py` is the only pre-existing change.
- [ ] Run `pip show slowapi numpy scipy baostock duckdb` to get installed versions.
- [ ] Record the versions for use in requirements.txt.

### Task 2: Update requirements.txt

- [ ] Add `slowapi` with the installed version.
- [ ] Add `numpy` with the installed version.
- [ ] Add `scipy` with the installed version.
- [ ] Add `baostock` with the installed version.
- [ ] Add `duckdb` with the installed version.
- [ ] Verify no duplicate entries.
- [ ] Keep existing entries and their versions unchanged.

### Task 3: Update CI workflow

- [ ] In `backend-test` job, replace `pip install fastapi uvicorn akshare pandas requests slowapi pytest` with `pip install -r backend/requirements.txt && pip install pytest`.
- [ ] In `api-health-check` job, add `uses: actions/checkout@v4` as the first step (currently missing, job has no source code).
- [ ] In `api-health-check` job, update the `Start backend` step: remove `cd backend`, use `pip install -r backend/requirements.txt -q` for install, and change the python command to `python -c "from backend.api.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8001)"`. Note: `ubuntu-latest` has Python 3 pre-installed, so no container needed.
- [ ] Ensure `frontend-build` job is unchanged.

### Task 4: Update README

- [ ] Find the "运行 > 后端" section in `README.md`.
- [ ] Change the startup command to:

```bash
conda activate tradesnake
python -m uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8001
```

- [ ] Add a brief note that the command should be run from the project root directory.
- [ ] Do not change other sections of README.

### Task 5: Update PROJECT_FACT_BASE

- [ ] In section 5.2, add a note that backend startup has been unified to `backend.api.main:app` from repo root.
- [ ] In section 5.3, add a note that CI now uses `requirements.txt`.
- [ ] Update section 6.1 to reflect the unified command.

### Task 6: Verify

- [ ] Run `python -m pytest backend/tests/ -v` from the repo root and record result.
- [ ] Run `python -c "from backend.api.main import app; print('import ok')"` from the repo root and record result.
- [ ] Verify `requirements.txt` has no syntax errors: `pip install --dry-run -r backend/requirements.txt 2>&1 | head -5`.
- [ ] Run `git diff -- backend/requirements.txt .github/workflows/ci.yml README.md docs/superpowers/plans/PROJECT_FACT_BASE.md` to review all changes.

### Task 7: Report

- [ ] Use the standard completion report format.
- [ ] Include verification command results.
- [ ] Note any pre-existing test failures.
- [ ] Recommend the next task (test scope unification: `backend/tests` vs `tests/backtester`).

---

## Verification

Required commands:

```bash
# Import check from repo root
python -c "from backend.api.main import app; print('import ok')"

# Existing tests must still pass
python -m pytest backend/tests/ -v

# Requirements file syntax
pip install --dry-run -r backend/requirements.txt 2>&1 | head -20

# Review all changes
git diff -- backend/requirements.txt .github/workflows/ci.yml README.md docs/superpowers/plans/PROJECT_FACT_BASE.md
```

---

## Completion Report Format

```markdown
## Summary
- State what changed and why.

## Verification
- `python -c "from backend.api.main import app"`: result.
- `python -m pytest backend/tests/ -v`: result (N passed, M failed, etc).
- `pip install --dry-run -r backend/requirements.txt`: result.

## Existing Issues Or Risks
- List pre-existing issues, unresolved risks, or state "None identified".

## Next Task Recommendation
- Recommend one concrete next task.
```
