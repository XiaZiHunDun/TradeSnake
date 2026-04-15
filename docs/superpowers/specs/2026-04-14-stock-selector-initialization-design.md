# StockSelector 初始化实现方案

> 日期：2026-04-14
> 目标：为 StockSelector 提供指数成分数据并完成初始化

---

## 一、现状问题

1. **StockSelector 已实例化** (`backend/api/main.py`)，但 `initialize()` 从未被调用
2. **指数成分数据缺失**：`data_manager` 没有获取沪深300/中证500/中证1000成分股的功能
3. **股票池为空**：所有池 (core/active/observe/temp) 都是空的

---

## 二、目标

在 `data_manager` 中添加指数成分获取功能，并在服务启动时调用 `StockSelector.initialize()` 完成股票池初始化。

---

## 三、数据流设计

```
启动流程：
1. data_manager.fetch_index_constituents()
   ↓ 获取 akshare: index_stock_cons_csindex('000300'), ('000905'), ('000852')
   ↓ 返回 { "hs300": [...], "zz500": [...], "zz1000": [...] }

2. StockSelector.initialize(stock_list, market_data, financial_data, index_data)
   ↓ 硬性排除 → 准入过滤 → 分层分类
   ↓ 沪深300/中证500 → 核心池 (300-350只)
   ↓ 中证1000 → 活跃池 (500-600只)
   ↓ 其他满足准入条件 → 观察池 (800-1200只)

3. CP 引擎通过 get_all_analysable_codes() 获取核心池+活跃池股票进行战力计算
```

---

## 四、实现内容

### 4.1 data_manager/fetcher.py 添加指数成分获取

```python
def fetch_index_constituents() -> Dict[str, List[Dict]]:
    """
    获取三大指数成分股

    Returns:
        {
            "hs300": [{"code": "600000", "name": "浦发银行", "weight": 0.5}, ...],
            "zz500": [...],
            "zz1000": [...],
        }
    """
    # 使用 akshare.index_stock_cons_csindex
    # 000300 = 沪深300, 000905 = 中证500, 000852 = 中证1000
```

### 4.2 data_manager/manager.py 添加聚合方法

在 `DataManager` 中添加 `get_index_constituents()` 方法，调用 `fetcher.fetch_index_constituents()`。

### 4.3 backend/api/main.py 启动时初始化 StockSelector

```python
# 在 lifespan() 中，selector 实例化之后，调用 initialize()
selector = get_stock_selector()

# 获取必要数据
stock_list = data_manager.get_stock_list()
market_data = data_manager.get_market_data()
financial_data = data_manager.get_financial_data()
index_data = data_manager.get_index_constituents()  # 新增

# 初始化
selector.initialize(stock_list, market_data, financial_data, index_data)
```

### 4.4 CP 引擎与 StockSelector 联动

CP 引擎的战力计算目标应改为 StockSelector 的 `get_all_analysable_codes()` 返回的股票（核心池+活跃池）。

---

## 五、代码对照

| 文件 | 现状 | 需要修改 |
|------|------|----------|
| `data_manager/fetcher.py` | 无指数获取功能 | 添加 `fetch_index_constituents()` |
| `data_manager/manager.py` | 无 `get_index_constituents()` | 添加方法 |
| `backend/api/main.py` | StockSelector 未初始化 | 调用 `selector.initialize()` |
| `backend/api/router.py` | `/api/refresh` 独立工作 | 可能需要与 selector 联动 |

---

## 六、验证指标

- [ ] 启动后 StockSelector 各池有股票
- [ ] 核心池 300-350 只，活跃池 500-600 只
- [ ] `/api/cp/top` 显示核心池股票
- [ ] CP 引擎只处理核心池+活跃池

---

## 七、风险

1. **指数成分获取失败**：需要设置缓存和重试机制
2. **初始化时间长**：2951只股票可能耗时较长，需要异步处理
3. **tradesnake.db 损坏**：使用 full-fetch-filter 绕过

---

## 八、不在本方案范围

- 盘中实时更新策略（Phase 5 已设计但暂不实现）
- 事件触发和临时池（盘中事件驱动）
- 再平衡逻辑（盘后批处理）
