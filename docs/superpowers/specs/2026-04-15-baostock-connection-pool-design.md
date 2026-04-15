# Baostock 连接池设计

## 概述

为 `FinancialDataFetcher` 添加 Baostock 连接池，避免每获取一只股票的财务数据就执行一次 `bs.login()`/`bs.logout()`。

**版本**: v1 | **状态**: 设计中

---

## 问题

当前 `_fetch_from_baostock(symbol)` 对每只股票执行：

```
bs.login() → query_profit_data → query_growth_data → query_balance_data → query_cash_flow_data → query_dividend_data → bs.logout()
```

1500 只股票 = **1500 次 login/logout 对**，日志中产生大量 `login success! / logout success!` 输出，且每次都重复认证，拖慢整体刷新速度。

---

## 解决方案

### 连接池架构

```
FinancialDataFetcher
└── _baostock_pool: BaoStockPool
    ├── pool_size: 5 (连接数)
    ├── max_reuses: 500 (每连接最大复用次数)
    └── _lock: threading.RLock (线程安全)

BaoStockPool
├── _sessions: List[BaoStockSession]  # 空闲连接列表
├── _busy_count: int                   # 繁忙连接计数
└── acquire() → BaoStockSession       # 借出连接
    release(session)                   # 归还连接

BaoStockSession
├── _bs: baostock instance
├── _reuses: int                       # 当前复用次数
├── _max_reuses: 500                   # 最大复用次数
├── _login()                           # 登录
├── query(...)
└── _logout()                          # 登出
```

### 复用策略

1. **池初始化**: `FinancialDataFetcher.__init__` 时创建 5 个已 login 的 `BaoStockSession`
2. **借出**: `_fetch_from_baostock` 调用 `pool.acquire()` 获取连接
3. **归还**: 用完后 `pool.release(session)` 归还
4. **自动重连**: 连接复用次数达到 500 或 query 失败时，执行 `logout` + 重新 `login`
5. **线程安全**: `acquire`/`release` 使用 `threading.RLock`

---

## 接口设计

### BaoStockSession

```python
class BaoStockSession:
    """封装单次 baostock 会话"""

    def __init__(self, max_reuses: int = 500):
        # 注意：使用模块级导入的 bs，不在 __init__ 中 import
        # （避免重复导入导致问题）
        self._bs = bs
        self._reuses = 0
        self._max_reuses = max_reuses
        self._logged_in = False
        self._login()

    def _login(self):
        """登录 baostock"""
        lg = self._bs.login()
        if lg.error_code != '0':
            raise ConnectionError(f"baostock login failed: {lg.error_msg}")
        self._logged_in = True

    def query(self, query_func, *args, **kwargs):
        """执行查询，自动重连"""
        if self._reuses >= self._max_reuses:
            self._relogin()
        try:
            result = query_func(*args, **kwargs)
            if result.error_code != '0':
                self._relogin()
                result = query_func(*args, **kwargs)
            self._reuses += 1
            return result
        except Exception:
            self._relogin()
            raise

    def _relogin(self):
        """重新登录（状态修复：先重置_logged_in再logout）"""
        was_logged_in = self._logged_in
        self._logged_in = False  # 先重置状态
        if was_logged_in:
            self._bs.logout()
        self._login()
        self._reuses = 0

    def logout(self):
        """登出"""
        if self._logged_in:
            self._bs.logout()
            self._logged_in = False
```

### BaoStockPool

```python
class BaoStockPool:
    """Baostock 连接池"""

    def __init__(self, pool_size: int = 5, max_reuses: int = 500):
        self._pool_size = pool_size
        self._max_reuses = max_reuses
        self._sessions: List[BaoStockSession] = []
        self._lock = threading.RLock()

    def _ensure_initialized(self):
        """延迟初始化连接池"""
        if not self._sessions:
            for _ in range(self._pool_size):
                self._sessions.append(BaoStockSession(max_reuses=self._max_reuses))

    def acquire(self) -> BaoStockSession:
        """获取一个连接"""
        with self._lock:
            self._ensure_initialized()
            # 优先返回空闲连接（简化：直接取第一个）
            session = self._sessions.pop(0)
            return session

    def release(self, session: BaoStockSession):
        """归还一个连接"""
        with self._lock:
            self._sessions.append(session)
```

### FinancialDataFetcher 改动

```python
class FinancialDataFetcher:
    def __init__(self):
        # ... 现有初始化 ...
        self._baostock_pool: BaoStockPool = None

    @property
    def _bs_pool(self) -> BaoStockPool:
        """延迟初始化的连接池"""
        if self._baostock_pool is None:
            self._baostock_pool = BaoStockPool(pool_size=5, max_reuses=500)
        return self._baostock_pool

    def _fetch_from_baostock(self, symbol: str) -> Optional[Dict]:
        # 现有逻辑不变，只是把 bs.login/query/logout 替换为池操作
        session = self._bs_pool.acquire()
        try:
            # 替换: lg = bs.login()
            # 替换: rs = bs.query_xxx(...)
            # 替换: bs.logout()
        finally:
            self._bs_pool.release(session)
```

---

## 数据流

```
刷新请求 (1500只股票)
    ↓
get_stock_data_api(limit=1500)
    ↓
get_full_stock_data()  [串行 for each stock]
    ↓
financial_fetcher.get_financial_data(symbol)
    ↓
_fetch_from_baostock(symbol)
    ↓
pool.acquire() → BaoStockSession  (第1次借出连接1)
    ↓
session.query(bs.query_profit_data, ...)
session.query(bs.query_growth_data, ...)
session.query(bs.query_balance_data, ...)
session.query(bs.query_cash_flow_data, ...)
session.query(bs.query_dividend_data, ...)
    ↓
pool.release(session)  (归还连接1，继续处理下一只)
    ↓
... 重复 300 次 (1500/5) ...
    ↓
连接1 达到 500 次复用 → 内部自动 relogin
```

---

## 预期效果

| 指标 | 改动前 | 改动后 |
|------|--------|--------|
| login/logout 次数 | 1500 对 | ~5 对（池大小） |
| 日志输出 | 3000+ 行 `login/logout success!` | ~10 行 |
| 1500 只股票获取耗时 | 50+ 分钟 | ~8 分钟（串行网络延迟） |
| 线程安全 | 无 | 线程安全 |
| API启动响应 | 数分钟等待 | **<1秒** |
| cp_engine股票数 | 0（启动时） | **300只**（预加载） |

---

## 改动文件

| 文件 | 改动内容 |
|------|----------|
| `backend/data_manager/fetcher.py` | 新增 `BaoStockSession`、`BaoStockPool` 类；改造 `_fetch_from_baostock`；新增 `get_market_cap_leaders` 重试逻辑 |
| `backend/engine/cp_engine/cp_engine.py` | 新增 `StockCP.from_precalculated()` 方法 |
| `backend/api/main.py` | 新增 `preload_cp_engine_from_history()` 快速预加载器 |

---

## 实现要点

1. **延迟初始化**: 连接池在第一次使用时才创建连接，避免启动时就占满资源
2. **线程安全**: `acquire`/`release` 使用 `RLock` 保护
3. **自动重连**: query 失败后自动 relogin，不污染池内其他连接
4. **复用上限**: 500 次后强制 relogin，防止 baostock 服务端超时
5. **兼容现有逻辑**: `_fetch_from_baostock` 的输入输出不变，只是内部实现改为池操作
6. **异常安全**: `try/finally` 确保连接一定归还
7. **快速预加载**: 从SQLite cp_history加载预计算分数，跳过 `calculate_scores()`

---

## 附加修复

### cp_engine启动为空
- **问题**: 背景刷新需8分钟，服务启动后长时间 `cp_engine.stocks=0`
- **方案**: 新增 `StockCP.from_precalculated()` + `preload_cp_engine_from_history()`
- **效果**: <1秒加载300只股票

### 东方财富API不稳定
- **问题**: `ak.stock_zh_a_spot_em()` 偶发失败
- **方案**: 3次重试 + 2/4秒指数退避
- **效果**: 失败时降级到随机抽样

### 数据库损坏
- **问题**: `tradesnake.db` 显示 "database disk image is malformed"
- **方案**: `sqlite3 .recover` + 重建
- **效果**: 恢复3424只股票

---

## 版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v1 | 2026-04-15 | 初始设计 |
| v2 | 2026-04-15 | 实现+附加cp_engine预加载+重试逻辑 |
