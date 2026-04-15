# StockSelector 初始化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 data_manager 中添加指数成分获取功能，并在服务启动时完成 StockSelector 初始化，使股票池正确分层（核心池300-350只、活跃池500-600只）。

**Architecture:** 在 data_manager.fetcher 中新增 IndexDataFetcher 类获取三大指数成分（沪深300/中证500/中证1000），通过 DataManager 聚合暴露。启动时将指数数据连同股票列表、行情、财务数据一起传给 StockSelector.initialize() 完成池初始化。

**Tech Stack:** akshare (index_stock_cons_csindex), SQLite (tradesnake.db), DuckDB (historical.duckdb)

---

## 文件结构

```
backend/data_manager/fetcher.py      # 新增 IndexDataFetcher 类
backend/data_manager/manager.py     # 新增 get_index_constituents() 方法
backend/api/main.py                  # 启动时初始化 StockSelector
```

---

### Task 1: 在 fetcher.py 中添加 IndexDataFetcher 类

**Files:**
- Modify: `backend/data_manager/fetcher.py` (在文件末尾 `StockDataFetcher` 类之前添加)

- [ ] **Step 1: 添加 IndexDataFetcher 类**

在 `fetcher.py` 文件末尾（约第598行，`class StockDataFetcher` 之前）添加：

```python
class IndexDataFetcher:
    """
    指数成分股获取器

    支持获取：
    - 沪深300 (000300)
    - 中证500 (000905)
    - 中证1000 (000852)
    """

    INDEX_CODES = {
        "hs300": "000300",
        "zz500": "000905",
        "zz1000": "000852",
    }

    def __init__(self):
        self._cache = None
        self._cache_time = None

    def get_index_constituents(self, force_refresh: bool = False) -> Dict[str, List[Dict]]:
        """
        获取三大指数成分股

        Args:
            force_refresh: 是否强制刷新

        Returns:
            {
                "hs300": [{"code": "600000", "name": "浦发银行", "weight": 0.5}, ...],
                "zz500": [...],
                "zz1000": [...],
            }
        """
        import os
        os.environ.pop('http_proxy', None)
        os.environ.pop('https_proxy', None)

        import akshare as ak

        result = {}
        for index_name, index_code in self.INDEX_CODES.items():
            try:
                df = ak.index_stock_cons_csindex(symbol=index_code)
                if df is not None and len(df) > 0:
                    stocks = []
                    for _, row in df.iterrows():
                        code = str(row['成分券代码']).zfill(6)  # 补齐6位
                        name = str(row['成分券名称']) if pd.notna(row['成分券名称']) else ""
                        stocks.append({"code": code, "name": name})
                    result[index_name] = stocks
                    print(f"获取 {index_name} ({index_code}): {len(stocks)} 只")
                else:
                    result[index_name] = []
                    print(f"获取 {index_name} 返回空数据")
            except Exception as e:
                print(f"获取 {index_name} 失败: {e}")
                result[index_name] = []

        return result
```

- [ ] **Step 2: 验证 akshare 返回格式**

Run:
```bash
python3 -c "
import os
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
import akshare as ak
import pandas as pd
df = ak.index_stock_cons_csindex(symbol='000300')
print('Columns:', df.columns.tolist())
print('Sample:', df.head(2).to_dict('records'))
print('Code type:', type(df.iloc[0]['成分券代码']))
"
```

Expected: 显示各指数成分股数量

---

### Task 2: 在 manager.py 中添加 get_index_constituents() 方法

**Files:**
- Modify: `backend/data_manager/manager.py`

- [ ] **Step 1: 在 DataManager.__init__() 中初始化 IndexDataFetcher**

在 `manager.py` 约第341行 `_stock_list_fetcher = StockListFetcher()` 之后添加：

```python
        self._index_fetcher = IndexDataFetcher()
```

- [ ] **Step 2: 在 DataManager 类中添加 get_index_constituents() 方法**

在 `get_stock_list()` 方法之后（约第471行之后）添加：

```python
    def get_index_constituents(self, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, List[Dict]]:
        """
        获取三大指数成分股

        Args:
            use_cache: 是否使用缓存
            force_refresh: 是否强制刷新

        Returns:
            {
                "hs300": [{"code": "600000", "name": "浦发银行"}, ...],
                "zz500": [...],
                "zz1000": [...],
            }
        """
        cache_key = "index_constituents"
        if use_cache and not force_refresh:
            cached = self._cache.get('static', cache_key)
            if cached:
                return cached

        data = self._index_fetcher.get_index_constituents(force_refresh=force_refresh)

        if data:
            self._cache.set('static', cache_key, data)
            return data

        return {}
```

- [ ] **Step 3: 验证方法存在**

Run:
```bash
cd /home/ailearn/projects/TradeSnake && python3 -c "
from backend.data_manager.manager import DataManager
dm = DataManager()
print('get_index_constituents 方法存在:', hasattr(dm, 'get_index_constituents'))
"
```

Expected: True

---

### Task 3: 在 main.py 启动时初始化 StockSelector

**Files:**
- Modify: `backend/api/main.py`

- [ ] **Step 1: 修改 lifespan() 中的 StockSelector 初始化**

找到 `lifespan()` 函数中 `selector = get_stock_selector()` 之后的代码（约第182-196行），修改为：

```python
    # 初始化StockSelector（基础实例化，完整初始化需要数据）
    selector = get_stock_selector()

    # 获取必要数据并初始化 StockSelector
    try:
        from backend.data_manager.manager import get_data_manager
        dm = get_data_manager()

        # 获取股票列表
        stock_list = dm.get_stock_list(use_cache=True, force_refresh=False)
        # 格式化股票列表 (转为 StockSelector 需要的格式)
        formatted_stock_list = []
        for s in stock_list:
            formatted_stock_list.append({
                "code": s.get("code", ""),
                "name": s.get("name", ""),
                "is_st": s.get("is_st", False),
                "listing_days": s.get("listing_days", 0),
                "in_hs300": False,  # 暂时设为 False，等指数同步
                "in_zz500": False,
                "in_zz1000": False,
            })

        # 获取指数成分
        index_data = dm.get_index_constituents(use_cache=True, force_refresh=False)

        # 获取市场数据（成交量等）
        market_data = {}

        # 获取财务数据
        financial_data = {}

        # 初始化 StockSelector
        if formatted_stock_list and index_data:
            selector.initialize(formatted_stock_list, market_data, financial_data, index_data)
            print(f"[启动] StockSelector 初始化完成: {selector.get_pool_stats()}")
        else:
            print(f"[启动] StockSelector 初始化跳过: stock_list={len(formatted_stock_list)}, index_data={bool(index_data)}")

    except Exception as e:
        print(f"[启动] StockSelector 初始化失败: {e}")
        import traceback
        traceback.print_exc()

    # 注册UpdateScheduler回调（用于联动data_manager更新调度）
    try:
        from backend.data_manager.update_scheduler import UpdateScheduler, StockSelectorCallback
        from backend.data_manager.manager import get_data_manager
        dm = get_data_manager()
        scheduler = UpdateScheduler(dm, None)  # 临时None，后续需要UpdateStrategyProvider
        callback = StockSelectorCallback(scheduler)
        selector.register_callback(callback)
        print("[启动] StockSelector 回调注册完成")
    except Exception as e:
        print(f"[启动] StockSelector 回调注册失败: {e}")
```

- [ ] **Step 2: 重启后端服务并验证**

Run:
```bash
cd /home/ailearn/projects/TradeSnake && pkill -f "uvicorn backend.api.main:app" && sleep 2 && nohup python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --workers 1 > /tmp/tradesnake.log 2>&1 & sleep 5 && curl --noproxy '*' -s http://localhost:8001/api/health
```

Expected: 服务正常启动

- [ ] **Step 3: 检查 StockSelector 池状态**

Run:
```bash
grep -E "StockSelector 初始化" /tmp/tradesnake.log | tail -5
```

Expected: 显示初始化完成和各池股票数量

---

### Task 4: 验证完整流程

**Files:**
- 无需修改文件

- [ ] **Step 1: 验证核心池和活跃池股票数量**

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

Expected: core=300-350, active=500-600, observe=800-1200

- [ ] **Step 2: 验证 get_all_analysable_codes() 返回正确数量**

Run:
```bash
python3 -c "
import sys
sys.path.insert(0, '/home/ailearn/projects/TradeSnake')
from backend.stock_selector import StockSelector
selector = StockSelector()
codes = selector.get_all_analysable_codes()
print(f'可分析股票 (核心+活跃): {len(codes)} 只')
"
```

Expected: 约 800-950 只

---

## 验证清单

- [ ] IndexDataFetcher.get_index_constituents() 返回正确数据
- [ ] DataManager.get_index_constituents() 方法存在且可用
- [ ] 服务启动时 StockSelector.initialize() 被调用
- [ ] 核心池: 300-350 只
- [ ] 活跃池: 500-600 只
- [ ] 观察池: 800-1200 只

---

## 风险处理

1. **akshare 获取失败**: 指数数据有缓存机制，首次失败后可重试
2. **初始化时间长**: 2951只股票初始分类可能耗时，后续可优化为异步
3. **tradesnake.db 损坏**: 使用 use_cache=True 和 full-fetch-filter 绕过
