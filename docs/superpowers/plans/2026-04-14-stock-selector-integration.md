# StockSelector 模块对接实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 StockSelector 与 CP 引擎、Recommender 的联动，使系统按股票池分层处理。

---

## 文件结构

```
backend/api/main.py                  # 注册 RecommenderCallback
backend/api/router.py               # 修改 /api/refresh 使用 get_all_analysable_codes
backend/stock_selector/__init__.py  # 可能需要导出相关类型
```

---

### Task 1: 修改 /api/refresh 只刷新核心池+活跃池股票

**Files:**
- Modify: `backend/api/router.py`

- [ ] **Step 1: 分析当前 /api/refresh 实现**

读取 `router.py` 中 `/api/refresh` 端点的实现（约第535-590行），了解：
- 如何获取股票数据
- 如何加载到 cp_engine

- [ ] **Step 2: 获取 StockSelector 可分析股票代码**

在 `/api/refresh` 开始处添加：
```python
# 获取 StockSelector 的核心池+活跃池股票
selector = get_stock_selector()
analysable_codes = set(selector.get_all_analysable_codes())
print(f"[刷新] StockSelector 可分析股票: {len(analysable_codes)} 只")
```

- [ ] **Step 3: 修改 get_stock_data_api 调用，限制范围**

找到 `get_stock_data_api(limit=limit)` 调用，修改为只获取可分析股票：
```python
# 获取 StockSelector 核心池+活跃池股票（不通过 get_stock_data_api 的 limit 限制）
stocks_data = [s for s in get_stock_data_api(limit=5000) if s.get('code') in analysable_codes]
```

---

### Task 2: 在 main.py 中注册 RecommenderCallback

**Files:**
- Modify: `backend/api/main.py`

- [ ] **Step 1: 在 lifespan() 中注册 RecommenderCallback**

在 StockSelector 初始化之后，添加：
```python
# 注册 Recommender 回调
try:
    from backend.recommender.recommend_engine import RecommenderCallback
    recommender_callback = RecommenderCallback(cp_engine)
    selector.register_recommender_callback(recommender_callback)
    print("[启动] RecommenderCallback 注册完成")
except Exception as e:
    print(f"[启动] RecommenderCallback 注册失败: {e}")
```

注意：`RecommenderCallback(cp_engine)` 需要传入 CP 引擎实例。

---

### Task 3: 验证 CP 引擎股票数量

**Files:**
- 无需修改文件

- [ ] **Step 1: 触发 /api/refresh 并检查结果**

Run:
```bash
curl --noproxy '*' -s -X POST http://localhost:8001/api/refresh
```

- [ ] **Step 2: 检查 CP 引擎股票数量**

Run:
```bash
curl --noproxy '*' -s http://localhost:8001/api/stats/market
```

Expected: stocks_count 约 800-1000（核心池+活跃池）

- [ ] **Step 3: 验证 StockSelector 池状态未被破坏**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, '/home/ailearn/projects/TradeSnake')
from backend.stock_selector import StockSelector
selector = StockSelector()
stats = selector.get_pool_stats()
print('StockSelector 池状态:')
for tier, count in stats.items():
    print(f'  {tier}: {count}')
"
```

---

## 验证清单

- [ ] `/api/refresh` 只刷新核心池+活跃池股票
- [ ] CP 引擎股票数量约 800-1000
- [ ] StockSelector 池状态正常
- [ ] RecommenderCallback 注册成功（日志中可见）
