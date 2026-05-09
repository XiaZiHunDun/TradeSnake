# 修复既有测试失败 + 统一测试 CI 覆盖范围

> **For Claude Code:** Execute this task continuously. Make routine engineering decisions yourself. Stop only when a stop condition is met.  
> **Fact base:** Read `docs/superpowers/plans/PROJECT_FACT_BASE.md` first.  
> **Template:** This task follows `docs/superpowers/plans/CLAUDE_CODE_TASK_TEMPLATE.md`.

---

## Goal

1. 修复 `backend/tests/` 下 9 个既有测试失败，使 `python -m pytest backend/tests/ -v` 全部通过。
2. 把 `tests/backtester/` 纳入 CI 测试范围。
3. 建立干净的测试基线，后续任务可以依赖"全绿"来判断是否有回归。

验收标准：

- `python -m pytest backend/tests/ -v` 全部通过（0 failed）。
- `python -m pytest tests/backtester/ -v` 能正常运行（记录通过/失败数量）。
- `.github/workflows/ci.yml` 的 `backend-test` job 同时覆盖两个测试目录。
- 不改变任何业务逻辑或生产代码行为。

---

## Context

### 问题 A：`test_cp_engine.py` 2 个失败

`StockCP.get_risk_level()` 已从中文改为英文返回值：

```python
# backend/engine/cp_engine/cp_engine.py 第 693-699 行
def get_risk_level(self) -> str:
    if self.risk_score >= 60:
        return 'high'
    elif self.risk_score >= 30:
        return 'medium'
    else:
        return 'low'
```

但测试仍期望中文：

- 第 82 行：`assert high_risk.get_risk_level() == '高风险'` -- 应改为 `== 'high'`
- 第 83 行：`assert low_risk.get_risk_level() in ['较低', '中等']` -- 应改为 `in ['low', 'medium']`
- 第 496 行：`assert high_risk.get_risk_level() == '高风险'` -- 应改为 `== 'high'`
- 第 505 行：`assert mid_risk.get_risk_level() in ['中等', '较低']` -- 应改为 `in ['medium', 'low']`
- 第 514 行：`assert low_risk.get_risk_level() in ['较低', '中等']` -- 应改为 `in ['low', 'medium']`

### 问题 B：`test_fusion.py` 7 个失败

`ProbabilityPrediction` dataclass 新增了两个必需字段：

```python
# backend/engine/probability_predictor/predictor.py
@dataclass
class ProbabilityPrediction:
    code: str
    name: str
    up_probability_3d: float
    up_probability_5d: float
    confidence: float
    confidence_interval_3d: List[float]   # <-- 新增必需字段
    confidence_interval_5d: List[float]   # <-- 新增必需字段
    risk_level: str
    features: Dict[str, float]
    model_version: str = "rule_v19.8"
```

测试的 `_create_mock_prob_pred` 方法没有传入 `confidence_interval_3d` 和 `confidence_interval_5d`。

修复方法：在 `_create_mock_prob_pred` 中补上这两个参数，使用合理的默认区间值。

### 问题 C：CI 测试覆盖范围

当前 CI 只运行：

```yaml
python -m pytest backend/tests/ -v
```

需要增加 `tests/backtester/`，使之也被 CI 覆盖。

---

## Scope

允许修改：

- `backend/tests/test_cp_engine.py` - 修复 risk_level 断言（5 处）
- `backend/tests/test_fusion.py` - 修复 ProbabilityPrediction 构造参数（1 处方法）
- `.github/workflows/ci.yml` - 增加 tests/backtester 到测试范围
- `docs/superpowers/plans/PROJECT_FACT_BASE.md` - 更新 5.4 测试范围条目

禁止修改：

- `backend/` 下非 tests 目录的 Python 源码
- `frontend/`
- `backend/api/router.py` - 有用户未提交改动

---

## Autonomy

Claude Code 可自主决定：

- `confidence_interval_3d` 和 `confidence_interval_5d` 的具体默认值（合理区间即可，如 `(0.4, 0.8)` 和 `(0.3, 0.9)`）。
- CI 中是否用单独一行 `python -m pytest tests/backtester/ -v` 还是合并为 `python -m pytest backend/tests/ tests/backtester/ -v`。
- 是否在 PROJECT_FACT_BASE 中同时更新测试基线通过率。

---

## Stop Conditions

遇到以下情况必须停下询问用户：

- 发现 `test_cp_engine.py` 或 `test_fusion.py` 的失败原因不是上述分析的根因。
- 修复后出现新的测试失败。
- `tests/backtester/` 中有大面积失败需要判断是否修复。
- 需要修改非 tests 目录的 Python 源码。

---

## Files

Modify:

- `backend/tests/test_cp_engine.py` - 5 处 risk_level 断言改为英文
- `backend/tests/test_fusion.py` - `_create_mock_prob_pred` 方法补齐 2 个字段
- `.github/workflows/ci.yml` - 测试命令增加 `tests/backtester/`
- `docs/superpowers/plans/PROJECT_FACT_BASE.md` - 更新 5.4 状态

Do not modify:

- `backend/` 下非 tests 目录的 `.py` 文件
- `frontend/` 目录
- `backend/api/router.py`

---

## Steps

### Task 1: Prepare

- [ ] Run `git status --short` and confirm no unexpected changes.
- [ ] Run `python -m pytest backend/tests/ -v --tb=line 2>&1 | tail -20` to confirm the 9 failures are exactly as described.

### Task 2: Fix test_cp_engine.py

- [ ] Line 82: Change `== '高风险'` to `== 'high'`.
- [ ] Line 83: Change `in ['较低', '中等']` to `in ['low', 'medium']`.
- [ ] Line 496: Change `== '高风险'` to `== 'high'`.
- [ ] Line 505: Change `in ['中等', '较低']` to `in ['medium', 'low']`.
- [ ] Line 514: Change `in ['较低', '中等']` to `in ['low', 'medium']`.
- [ ] Run `python -m pytest backend/tests/test_cp_engine.py -v` to confirm all 30 tests pass.

### Task 3: Fix test_fusion.py

- [ ] In `_create_mock_prob_pred` method (around line 41-52), add `confidence_interval_3d` and `confidence_interval_5d` parameters to the `ProbabilityPrediction()` constructor call. Use reasonable default values like `[0.4, 0.8]` and `[0.3, 0.9]`.
- [ ] Run `python -m pytest backend/tests/test_fusion.py -v` to confirm all 10 tests pass.

### Task 4: Verify backend/tests baseline

- [ ] Run `python -m pytest backend/tests/ -v` and confirm 0 failures.
- [ ] Record exact pass count.

### Task 5: Check tests/backtester status

- [ ] Run `python -m pytest tests/backtester/ -v --tb=short 2>&1 | tail -40` and record results.
- [ ] If all pass, proceed. If some fail, record which tests fail and the root cause but do NOT fix them in this task (they may need separate design).

### Task 6: Update CI to include tests/backtester

- [ ] In `.github/workflows/ci.yml`, update the `backend-test` job's pytest command to also include `tests/backtester/`:

```yaml
python -m pytest backend/tests/ tests/backtester/ -v
```

- [ ] Ensure `pip install -r backend/requirements.txt` is still used (it was fixed in the previous task).

### Task 7: Update PROJECT_FACT_BASE

- [ ] In section 5.4, mark the test scope issue as resolved: CI now covers both `backend/tests/` and `tests/backtester/`.
- [ ] Add a new subsection or note recording the current test baseline (e.g., "backend/tests: N passed, tests/backtester: M passed, K failed").

### Task 8: Final Verification

- [ ] Run `python -m pytest backend/tests/ tests/backtester/ -v --tb=short 2>&1 | tail -30` and record final results.
- [ ] Run `git diff -- backend/tests/ .github/workflows/ci.yml docs/superpowers/plans/PROJECT_FACT_BASE.md` to review all changes.

### Task 9: Report

- [ ] Use the standard completion report format.
- [ ] Include full pytest output summary.
- [ ] Note any tests/backtester failures and their causes.
- [ ] Recommend the next task.

---

## Verification

Required commands:

```bash
# backend/tests must be fully green
python -m pytest backend/tests/ -v

# tests/backtester status
python -m pytest tests/backtester/ -v --tb=short

# Combined (what CI will run)
python -m pytest backend/tests/ tests/backtester/ -v --tb=short

# Review changes
git diff -- backend/tests/ .github/workflows/ci.yml docs/superpowers/plans/PROJECT_FACT_BASE.md
```

---

## Completion Report Format

```markdown
## Summary
- State what changed and why.

## Verification
- `python -m pytest backend/tests/ -v`: N passed, 0 failed.
- `python -m pytest tests/backtester/ -v`: M passed, K failed (list failures if any).
- CI updated to cover both directories.

## Existing Issues Or Risks
- List any tests/backtester failures that need separate attention.

## Next Task Recommendation
- Recommend one concrete next task.
```
