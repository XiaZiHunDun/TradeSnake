# 任务：修复 fusion.py 波动率过滤单位错误与 test_fusion.py 残余断言失败

> 日期：2026-04-27  
> 类型：Bug Fix  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：`2026-04-26-fix-tests-and-ci-scope-implementation.md`（已完成）

---

## 目标

修复 `backend/tests/test_fusion.py` 中最后 3 个失败测试，使 `backend/tests/` 达到全绿基线。

---

## 上下文

### 当前测试状态

```
backend/tests/test_fusion.py: 7 passed, 3 failed
```

3 个失败：
- `test_fuse_batch_filters_low_probability` — `assert len(results) == 1` 实际 `len([]) == 0`
- `test_fuse_batch_sorted_by_fused_score` — `assert len(results) == 3` 实际 `len([]) == 0`
- `test_to_dict` — `assert 'score_breakdown' in result_dict` 失败

### 根因分析

**Bug A：`FILTER_MAX_VOLATILITY` 单位换算错误**（影响前 2 个测试）

文件：`backend/recommender/fusion.py` 第 103-105 行

```python
# 波动率过滤：StockCP.volatility_20d 存储年化波动率(%)，这里转换为日波动率阈值
# 40% 年化 ≈ 40 / sqrt(252) ≈ 2.52% 日波动率（与 probability_predictor 的 40 阈值单位一致）
FILTER_MAX_VOLATILITY = 40 / (252 ** 0.5)  # ~2.52% 日波动率上限
```

证据链：

1. `_calc_volatility()` 返回年化波动率 %：`return std * np.sqrt(250) * 100`
   - 见 `backend/engine/probability_predictor/features.py:136` 和 `backend/engine/gain_predictor/features.py:152`
2. `GLOBAL_AVG_VOLATILITY = 25.0` — 即 25% 年化（两个模块均如此）
3. `probability_predictor` 对同类数据使用年化阈值：`if volatility > 40: risk='high'`（第 143-144 行）
4. fusion 的注释自己也写了"存储年化波动率(%)"，但却把阈值除以 sqrt(252) 变成了 ~2.52（日度 %）
5. `_get_filter_reason()` 直接拿 `stock.volatility_20d`（年化 %）与 2.52（日度 %）比较 → 单位不匹配
6. 测试 mock `stock.volatility_20d = 25.0` 是合理的年化值 → 25 > 2.52 → 所有股票被波动率过滤 → `fuse_batch` 返回空列表

正确修复：`FILTER_MAX_VOLATILITY = 40` —— 保持年化 % 单位，与 probability_predictor 的 40 阈值保持一致。

**Bug B：`to_dict()` 已重构但测试未同步**（影响第 3 个测试）

`FusionResult` 已从 `score_breakdown` dict 重构为独立字段 `cp_score`/`gain_score`/`prob_score`。  
`to_dict()` 输出这三个独立字段，不含 `score_breakdown`。  
`docs/plans/recommender/ISSUES.md` 标记该问题"已修复"，但测试断言仍为旧版。

---

## 执行原则

- 自主执行，无需询问用户。
- 不修改任何业务逻辑或融合公式。
- 只修正单位错误和过时断言。
- 每步完成后运行验证命令。

---

## 范围

### 允许修改

| 文件 | 修改内容 |
|------|----------|
| `backend/recommender/fusion.py` | 修复 `FILTER_MAX_VOLATILITY` 值和注释，修复 `FusionResult.volatility_20d` 注释 |
| `backend/tests/test_fusion.py` | 修复 `test_to_dict` 中 `score_breakdown` 断言 |
| `docs/plans/recommender/CHECKLIST.md` | 更新 volatility 阈值行和 score_breakdown 行 |
| `docs/plans/recommender/ISSUES.md` | 更新 score_breakdown 问题状态 |
| `docs/superpowers/plans/PROJECT_FACT_BASE.md` | 更新测试基线、记录 volatility 修复 |

### 禁止修改

- 融合公式权重、过滤条件逻辑结构、数据库 schema
- `backend/api/router.py`（用户已有未提交改动）
- 任何前端文件
- 产品范围或战力公式

---

## 自主决策

Claude Code 可以自主决定：
- 注释措辞的具体写法
- `test_to_dict` 中断言的具体字段检查方式（只要覆盖 `cp_score`/`gain_score`/`prob_score`）
- 文档更新的措辞

## 停止条件

以下情况必须停止并报告：
- `FILTER_MAX_VOLATILITY` 修改后导致其他已通过测试失败
- 发现 `_get_filter_reason` 有其他未预期的过滤逻辑问题
- 需要修改融合公式或权重配置

---

## 步骤

### Step 1：准备

```bash
git status --short
```

识别并保护已有改动。

### Step 2：修复 `FILTER_MAX_VOLATILITY` 单位错误

文件：`backend/recommender/fusion.py`

将：
```python
# 波动率过滤：StockCP.volatility_20d 存储年化波动率(%)，这里转换为日波动率阈值
# 40% 年化 ≈ 40 / sqrt(252) ≈ 2.52% 日波动率（与 probability_predictor 的 40 阈值单位一致）
FILTER_MAX_VOLATILITY = 40 / (252 ** 0.5)  # ~2.52% 日波动率上限
```

改为：
```python
# 波动率过滤：年化波动率上限 40%（与 probability_predictor 的 40 阈值单位一致）
FILTER_MAX_VOLATILITY = 40
```

同时修复 `FusionResult.volatility_20d` 的注释：

将：
```python
volatility_20d: float  # 20日波动率 (%，日度，与 FILTER_MAX_VOLATILITY 阈值单位一致)
```

改为：
```python
volatility_20d: float  # 20日波动率 (%，年化)
```

### Step 3：修复 `test_to_dict` 断言

文件：`backend/tests/test_fusion.py`

将：
```python
assert 'score_breakdown' in result_dict
```

改为对三个独立得分字段的断言：
```python
assert 'cp_score' in result_dict
assert 'gain_score' in result_dict
assert 'prob_score' in result_dict
```

### Step 4：验证 test_fusion.py 全绿

```bash
python -m pytest backend/tests/test_fusion.py -v
```

预期：10 passed, 0 failed。

### Step 5：验证 backend/tests/ 整体

```bash
python -m pytest backend/tests/ -v --ignore=backend/tests/test_routes.py
```

确认无回归。（test_routes.py 因 lifespan 初始化超时问题排除，非本次范围。）

### Step 6：验证 tests/backtester/ 无回归

```bash
python -m pytest tests/backtester/ -v
```

预期：48 passed, 0 failed。

### Step 7：更新文档

1. `docs/plans/recommender/CHECKLIST.md`：
   - 将 `- [ ] volatility_20d <= 2.52%` 改为 `- [x] volatility_20d <= 40%（年化，与 probability_predictor 一致）`
   - 将 `- [ ] score_breakdown 字段一致性` 改为 `- [x] score_breakdown 已拆分为 cp_score/gain_score/prob_score`

2. `docs/plans/recommender/ISSUES.md`：
   - 添加一行记录 `FILTER_MAX_VOLATILITY` 单位修复

3. `docs/superpowers/plans/PROJECT_FACT_BASE.md`：
   - 更新 5.4 测试基线：`backend/tests/`: 全绿（除 test_routes.py 因 lifespan 超时排除外）
   - 在 5.x 中记录 volatility 单位修复

### Step 8：最终验证

```bash
python -m pytest backend/tests/test_fusion.py -v
python -m pytest backend/tests/ -v --ignore=backend/tests/test_routes.py
python -m pytest tests/backtester/ -v
git diff --stat
```

---

## 验证标准

| 检查项 | 预期 |
|--------|------|
| `test_fusion.py` | 10 passed, 0 failed |
| `backend/tests/`（不含 test_routes） | 全绿 |
| `tests/backtester/` | 48 passed, 0 failed |
| `FILTER_MAX_VOLATILITY` 值 | 40（年化 %） |
| `to_dict()` 输出 | 含 `cp_score`/`gain_score`/`prob_score`，不含 `score_breakdown` |
| git diff 范围 | 仅限上述允许修改的文件 |

---

## 报告格式

```
Summary
  修改了什么、修复了哪些测试

Verification
  各 pytest 命令输出摘要

Existing Issues Or Risks
  残留问题（如 test_routes.py 超时等）

Next Task Recommendation
  建议下一步做什么
```

---

## 附注：已知但不在本次范围的问题

1. **`StockCP.volatility_20d` 在生产环境始终为 0**：`filler.py._create_stock_cp()` 调用 `create_stock_from_raw()` 时未传入 `volatility_20d`，导致波动率过滤形同虚设。这是一个功能完整性问题，需要单独的设计任务。

2. **`buy_analyzer.py` 和 `prompts.py` 的波动率阈值 8**：这两个文件用 `volatility > 8` 判断"偏高"，如果数据是年化 %（大多数股票 20-40%），则几乎所有股票都会触发。但因生产中默认值为 0，实际不影响。需在后续 volatility 补齐任务中统一处理。

3. **`test_routes.py` 的 lifespan 超时问题**：44 个测试因服务初始化约需 60 秒而难以快速验证。需单独评估是否使用 mock 或调整超时。
