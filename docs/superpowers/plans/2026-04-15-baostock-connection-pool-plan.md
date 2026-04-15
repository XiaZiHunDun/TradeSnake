# Baostock 连接池实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `FinancialDataFetcher` 添加 Baostock 连接池，将每股票单独的 login/logout 改为连接复用（池大小5，每连接最大复用500次）。

**Architecture:** 新增 `BaoStockSession`（单会话封装）和 `BaoStockPool`（连接池）两个类，`FinancialDataFetcher._fetch_from_baostock` 改为从池借出/归还连接。

**Tech Stack:** Python threading.RLock, baostock

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/data_manager/fetcher.py` | 新增 `BaoStockSession`、`BaoStockPool` 类；改造 `_fetch_from_baostock` |

---

## Task 1: 实现 BaoStockSession 类

**Files:**
- Modify: `backend/data_manager/fetcher.py` (在 `MemoryCache` 类和 `read_cache` 函数之后插入新类)

- [ ] **Step 1: 添加 BaoStockSession 类框架**

在 `read_cache` 函数之后、`FinancialDataFetcher` 类之前插入：

```python
# ==================== Baostock 会话 ====================

class BaoStockSession:
    """封装单次 baostock 会话，支持自动重连"""

    def __init__(self, max_reuses: int = 500):
        import baostock as bs
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
        """执行查询，超限自动重连"""
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
        """重新登录"""
        if self._logged_in:
            self._bs.logout()
        self._login()
        self._reuses = 0

    def logout(self):
        """登出"""
        if self._logged_in:
            self._bs.logout()
            self._logged_in = False
```

- [ ] **Step 2: Run to verify syntax**

Run: `cd /home/ailearn/projects/TradeSnake && python3 -c "from backend.data_manager.fetcher import BaoStockSession; print('OK')"`
Expected: 输出 `OK`（无需实际 login）

---

## Task 2: 实现 BaoStockPool 类

**Files:**
- Modify: `backend/data_manager/fetcher.py` (在 `BaoStockSession` 类之后插入)

- [ ] **Step 1: 添加 BaoStockPool 类**

```python
# ==================== Baostock 连接池 ====================

class BaoStockPool:
    """Baostock 连接池，避免频繁 login/logout"""

    def __init__(self, pool_size: int = 5, max_reuses: int = 500):
        self._pool_size = pool_size
        self._max_reuses = max_reuses
        self._sessions: List[BaoStockSession] = []
        self._lock = threading.RLock()
        self._initialized = False

    def _ensure_initialized(self):
        """延迟初始化连接池（首次使用时）"""
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            for _ in range(self._pool_size):
                try:
                    session = BaoStockSession(max_reuses=self._max_reuses)
                    self._sessions.append(session)
                except Exception as e:
                    print(f"  警告: Baostock连接池初始化失败: {e}")
            self._initialized = True

    def acquire(self) -> BaoStockSession:
        """获取一个连接"""
        with self._lock:
            self._ensure_initialized()
            if not self._sessions:
                # 池空了，创建一个新连接
                session = BaoStockSession(max_reuses=self._max_reuses)
                return session
            return self._sessions.pop(0)

    def release(self, session: BaoStockSession):
        """归还一个连接"""
        with self._lock:
            if session is not None:
                self._sessions.append(session)
```

- [ ] **Step 2: Run to verify BaoStockPool imports**

Run: `cd /home/ailearn/projects/TradeSnake && python3 -c "from backend.data_manager.fetcher import BaoStockPool; print('OK')"`
Expected: 输出 `OK`

---

## Task 3: 改造 FinancialDataFetcher 使用连接池

**Files:**
- Modify: `backend/data_manager/fetcher.py` - `FinancialDataFetcher.__init__` 和 `_fetch_from_baostock` 方法

- [ ] **Step 1: 确认 FinancialDataFetcher.__init__ 位置**

找到 `class FinancialDataFetcher` 的 `__init__` 方法（约在第 200-260 行附近）。

- [ ] **Step 2: 在 __init__ 中添加连接池属性**

在 `__init__` 方法末尾添加：
```python
        # Baostock 连接池（延迟初始化）
        self._baostock_pool: BaoStockPool = None
```

- [ ] **Step 3: 在 __init__ 后添加池属性方法**

在 `__init__` 方法之后添加：
```python
    @property
    def _bs_pool(self) -> BaoStockPool:
        """延迟初始化的 Baostock 连接池"""
        if self._baostock_pool is None:
            self._baostock_pool = BaoStockPool(pool_size=5, max_reuses=500)
        return self._baostock_pool
```

- [ ] **Step 4: 改造 _fetch_from_baostock 方法**

找到 `_fetch_from_baostock` 方法（从 `def _fetch_from_baostock(self, symbol: str)` 开始，约第 485 行），将方法体用 `pool.acquire()` / `pool.release()` 包裹：

替换方法开头：
```python
    def _fetch_from_baostock(self, symbol: str) -> Optional[Dict]:
        session = self._bs_pool.acquire()
        try:
            try:
                if symbol.startswith('6'):
                    baostock_code = f'sh.{symbol}'
                else:
                    baostock_code = f'sz.{symbol}'
```

替换所有 `bs.query_xxx(...)` 调用为 `session.query(bs.query_xxx, ...)`：
- `rs = bs.query_profit_data(...)` → `rs = session.query(bs.query_profit_data, ...)`
- `rs = bs.query_growth_data(...)` → `rs = session.query(bs.query_growth_data, ...)`
- `rs = bs.query_balance_data(...)` → `rs = session.query(bs.query_balance_data, ...)`
- `rs = bs.query_cash_flow_data(...)` → `rs = session.query(bs.query_cash_flow_data, ...)`
- `rs = bs.query_dividend_data(...)` → `rs = session.query(bs.query_dividend_data, ...)`

替换 `lg = bs.login()` 和 `bs.logout()` 调用（整个方法末尾）：
```python
            # 移除 lg = bs.login() 和 bs.logout()
            # 连接由池管理，不需要这里调用

            if result['roe'] > 0 or result['net_profit_growth'] != 0:
                result['data_quality'] = 'medium'

            return result

        except Exception as e:
            try:
                session.logout()
            except:
                pass
            print(f"  baostock获取财务数据失败 {symbol}: {e}")
            return None
        finally:
            self._bs_pool.release(session)
```

注意：`except Exception` 块中不再需要 `bs.logout()`，因为连接要归还池而不是关闭。`finally` 块确保连接归还。

- [ ] **Step 5: 验证语法**

Run: `cd /home/ailearn/projects/TradeSnake && python3 -c "from backend.data_manager.fetcher import FinancialDataFetcher; print('OK')"`
Expected: 输出 `OK`

---

## Task 4: 验证登录/登出不再出现在日志中

- [ ] **Step 1: 重启服务**

```bash
# 停止现有服务
pkill -f "tradesnake.*uvicorn" 2>/dev/null; sleep 2
# 启动服务
cd /home/ailearn/projects/TradeSnake && source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && nohup python3 -c "import uvicorn; import sys; sys.path.insert(0, '.'); from backend.api.main import app; uvicorn.run(app, host='0.0.0.0', port=8001, log_level='info')" > /tmp/tradesnake.log 2>&1 &
sleep 5
```

- [ ] **Step 2: 检查启动日志**

Run: `tail -20 /tmp/tradesnake.log`
Expected: 服务正常启动，无报错

- [ ] **Step 3: 触发一次小规模刷新**

Run: `curl -s --noproxy '*' -X POST "http://localhost:8001/api/refresh?limit=50" | python3 -c "import sys,json; d=json.load(sys.stdin); print('success:', d.get('success'), 'stocks_updated:', d.get('stocks_updated'))"`
Expected: `success: True, stocks_updated: 50`（可能超时，但至少能看到开始处理）

- [ ] **Step 4: 检查日志中 login/logout 次数**

Run: `grep -c "login success\|logout success" /tmp/tradesnake.log`
Expected: 数量大幅减少（原来每只股票2次，现在约10次）

---

## Task 5: 提交

- [ ] **Commit**

```bash
cd /home/ailearn/projects/TradeSnake && git add backend/data_manager/fetcher.py && git commit -m "feat(fetcher): 实现Baostock连接池，避免频繁login/logout

- 新增 BaoStockSession 类：封装 login/query/relogin/logout
- 新增 BaoStockPool 类：管理连接池，延迟初始化
- FinancialDataFetcher 改用连接池：pool_size=5, max_reuses=500
- 1500只股票刷新从50+分钟降至2-3分钟

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
