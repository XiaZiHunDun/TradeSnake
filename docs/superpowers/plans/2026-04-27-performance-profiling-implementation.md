# 任务：性能 Profiling — DuckDB 查询 + CP 批量计算

> 日期：2026-04-27  
> 类型：Performance Analysis + Optimization（中等风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：无硬性前置，独立可执行

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

**本任务分两阶段**：先 Profile 分析，再根据结果做安全优化。不做投机性优化——先证明瓶颈在哪，再修。

---

## Goal

1. 创建性能 profiling 脚本，量化以下热路径的实际耗时：
   - `CPEngine.calculate_all()` 对 200 只股票的计算时间
   - `DuckDBStore.get_klines_bulk()` 批量查询时间
   - `/api/refresh` 完整刷新流程（fetch + compute + save）
   - `/api/cp/top` 响应时间

2. 根据 profiling 结果，实施 **确定性优化**（不改变计算结果的优化）

完成后：有量化数据支撑的性能报告 + 至少一项已验证的性能改进。

---

## Context

### 已知的性能相关代码

#### CP 计算热路径 (`cp_engine.py` line 1029+)

```python
def calculate_all(self, use_multi_day_momentum=True):
    # 1. 可选：calc_momentum_5d（读 history）
    # 2. 收集原始分数
    # 3. _robust_normalize（numpy 百分位裁剪）
    # 4. 可选：get_bulk_minute_data（实时因子，交易时间内）
    # 5. 循环每只股票：加权求和 + 风险惩罚
```

#### DuckDB 查询（duckdb_store.py）

```python
def get_klines_bulk(self, codes: List[str], days=60):
    # 文件锁 → 单连接 → 单次 SQL IN (...) → 按 code 分组
    # 用于预测引擎全市场扫描

def get_klines(self, code, start_date, end_date, limit=1000):
    # 文件锁 → 连接 → 单股查询 → 返回
```

#### 刷新流程 (`system.py` refresh)

```
fetch_all_market_data → compute_cp_for_all → save_to_db + cache
```

#### 已知优化机会

1. **文件锁开销**: 每次 DuckDB 操作都 `_acquire_lock()`（flock），高频场景下可能成为瓶颈
2. **重复 normalize**: `calculate_all` 每次调用都重新归一化，如果股票列表不变可缓存
3. **bulk_minute_data**: 交易时间内每次 refresh 都查全市场分钟数据
4. **numpy 导入**: 如果 numpy 在热路径中按需导入，可能有开销

---

## Scope

Allowed changes:

- 创建 `scripts/profile_performance.py`（独立 profiling 脚本）
- 修改 `backend/engine/cp_engine/cp_engine.py`（确定性优化）
- 修改 `backend/data_manager/duckdb_store.py`（确定性优化）
- 修改 `backend/api/routers/system.py`（refresh 流程优化，如缓存判断）

Out of scope:

- 不改变 CP 公式的计算结果（优化后数值必须相同）
- 不改变 API 行为或响应格式
- 不引入新的外部依赖（可以用标准库 `time`, `cProfile`, `functools.lru_cache`）
- 不修改 DuckDB schema 或数据文件

---

## Autonomy

Claude Code 可以自主决定：

- profiling 脚本的具体实现方式
- 哪些优化值得做（基于实际数据，如果某步骤只占 1% 时间则跳过）
- 缓存策略的细节（如 LRU 容量、过期时间）
- 是否使用 `@functools.lru_cache` 或自定义缓存

---

## Stop Conditions

- profiling 需要真实数据库文件（`data/historical.duckdb`）但不存在 → 跳过 DuckDB 部分
- 优化导致 `calculate_all` 结果数值不一致 → 回退
- 优化导致测试失败 → 回退

---

## Steps

### Phase 1: Profiling

#### Step 1: 创建 profiling 脚本

- [ ] 创建 `scripts/profile_performance.py`
- [ ] 实现以下 benchmark：

```python
"""性能 profiling 脚本 — 量化关键路径耗时"""
import time
import cProfile
import pstats
from io import StringIO

def profile_cp_calculate_all():
    """Profile CPEngine.calculate_all()"""
    from backend.engine.cp_engine import CPEngine
    # 用 mock 数据构造 200 只股票
    engine = CPEngine()
    # 添加测试数据...
    
    start = time.perf_counter()
    for _ in range(10):  # 10 次取平均
        result = engine.calculate_all()
    elapsed = (time.perf_counter() - start) / 10
    print(f"calculate_all (200 stocks): {elapsed*1000:.1f}ms avg")

def profile_duckdb_bulk():
    """Profile DuckDB bulk query"""
    from backend.data_manager.duckdb_store import get_duckdb_store
    store = get_duckdb_store()
    codes = [...]  # 从实际 DB 获取
    
    start = time.perf_counter()
    result = store.get_klines_bulk(codes[:50], days=60)
    elapsed = time.perf_counter() - start
    print(f"get_klines_bulk (50 stocks, 60 days): {elapsed*1000:.1f}ms")

def profile_normalize():
    """Profile _robust_normalize"""
    import numpy as np
    from backend.engine.cp_engine import CPEngine
    engine = CPEngine()
    data = list(np.random.uniform(0, 100, 200))
    
    start = time.perf_counter()
    for _ in range(1000):
        engine._robust_normalize(data)
    elapsed = (time.perf_counter() - start) / 1000
    print(f"_robust_normalize (200 values): {elapsed*1000:.3f}ms avg")

if __name__ == '__main__':
    profile_normalize()
    profile_cp_calculate_all()
    # profile_duckdb_bulk()  # 需要真实 DB
```

#### Step 2: 运行 profiling

- [ ] `python scripts/profile_performance.py`
- [ ] 如果有真实 DuckDB 文件，也运行 DuckDB benchmark
- [ ] 记录结果到报告中
- [ ] 用 `cProfile` 找出 `calculate_all` 中最耗时的函数

### Phase 2: 确定性优化

根据 profiling 结果，选择实施以下优化（**只做有数据支撑的优化**）：

#### 可能的优化 A: normalize 结果缓存

如果 `_robust_normalize` 被同一组数据多次调用：
- [ ] 添加脏标记：仅当 stocks 列表变化时重新归一化
- [ ] 验证：结果不变

#### 可能的优化 B: 减少 DuckDB 文件锁频率

如果文件锁是主要瓶颈（单线程场景下可能不是）：
- [ ] 对只读操作使用 shared lock 池或连接复用
- [ ] 验证：测试通过

#### 可能的优化 C: calculate_all 中的循环优化

如果逐股票循环是瓶颈：
- [ ] 用 numpy 向量化加权求和替代 Python 循环
- [ ] 验证：结果数值相同（tolerance < 1e-6）

#### 可能的优化 D: refresh 流程的增量计算

如果 refresh 中大部分时间在重复计算未变化的股票：
- [ ] 添加"仅计算价格变化的股票"模式（可选参数）
- [ ] 验证：API 行为不变

### Phase 3: 验证

- [ ] 运行 profiling 脚本对比优化前后
- [ ] `python -m pytest backend/tests/test_cp_engine.py -v`
- [ ] `python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py`
- [ ] 记录优化效果

---

## Verification

```bash
# profiling 脚本能运行
python scripts/profile_performance.py

# 优化后测试通过
python -m pytest backend/tests/test_cp_engine.py -v
python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py

# 数值一致性（如果做了 calculate_all 优化）
python -c "
from backend.engine.cp_engine import CPEngine
engine = CPEngine()
# 构造相同输入，对比优化前后输出
"
```

---

## Completion Report Format

```markdown
## Profiling Results

| 路径 | 耗时 | 占比 | 瓶颈分析 |
|------|------|------|---------|
| calculate_all (200 stocks) | Xms | - | ... |
| _robust_normalize | Xms | Y% | ... |
| get_klines_bulk (50 stocks) | Xms | - | ... |

## Optimizations Applied

| 优化 | 修改文件 | 改进幅度 | 验证 |
|------|---------|---------|------|
| ... | ... | X% faster | tests pass |

## Optimizations NOT Applied (with reason)

| 优化 | 原因 |
|------|------|
| ... | profiling 显示仅占 N%，不值得复杂化 |

## Verification
- 测试结果
- 数值一致性验证

## Remaining Opportunities
- 需要更多数据或架构变更的优化建议
```
