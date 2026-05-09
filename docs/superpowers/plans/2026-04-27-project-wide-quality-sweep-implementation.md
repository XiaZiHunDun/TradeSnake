# 任务：项目全面质量扫盘 — 一次性修复所有已知问题

> 日期：2026-04-27  
> 类型：Quality Sweep（跨模块批量修复）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：`2026-04-27-fix-fusion-filter-and-tests-implementation.md`（已完成）

---

## 目标

一次性修复项目中所有已发现的代码质量、测试、CI、前端 Bug 和文档问题。共 9 个大类、约 50+ 处改动。完成后项目应达到：

- 所有可运行测试全绿（排除需要网络/完整数据的集成测试）
- CI pipeline 中所有检查可以真实反映代码健康状态
- 无 bare `except:` 残留
- 导入路径全项目统一
- 依赖文件与实际使用一致
- 文档与代码版本一致

---

## 执行原则

- **自主执行全部步骤，不需要中途询问用户**。
- 每个 Group 完成后立即运行对应验证命令，确认无回归再进入下一个 Group。
- 如果某个 Group 遇到无法自主解决的问题（如需要修改业务逻辑/公式），**跳过该项并记录到报告中**，继续其他 Group。
- 保护已有的 `backend/api/router.py` 用户未提交改动（该文件只允许删除 `Optional` 未使用导入，不动其他内容）。

---

## Group A：后端导入路径统一（10 个文件）

所有测试文件统一使用 `from backend.xxx` 导入，移除 `sys.path` hack。

### A1. `backend/tests/test_routes.py`

移除第 9-12 行的 `sys.path.insert` 和 `from api.main import app`。改为：
```python
from backend.api.main import app
```

同时更新模块级的 `client = TestClient(app)` 不变。

### A2. `backend/tests/test_history.py`

移除 `sys.path` hack。将所有 `from engine.xxx` 改为 `from backend.engine.xxx`。
同时更新所有 `patch('engine.xxx')` 为 `patch('backend.engine.xxx')`。

### A3. `backend/data_manager/tests/`（8 个文件）

以下文件全部需要：移除 `sys.path.insert` 行，把 `from data_manager.xxx` 改为 `from backend.data_manager.xxx`。

| 文件 | 当前导入 | 改为 |
|------|---------|------|
| `test_adjuster.py` | `from data_manager.adjuster import ...` | `from backend.data_manager.adjuster import ...` |
| `test_backup.py` | `from data_manager.backup import ...` | `from backend.data_manager.backup import ...` |
| `test_batcher.py` | `from data_manager.batcher import ...` | `from backend.data_manager.batcher import ...` |
| `test_circuit_breaker.py` | `from data_manager.circuit_breaker import ...` | `from backend.data_manager.circuit_breaker import ...` |
| `test_cleaner.py` | `from data_manager.cleaner import ...` | `from backend.data_manager.cleaner import ...` |
| `test_duckdb_store.py` | `from data_manager.duckdb_store import ...` | `from backend.data_manager.duckdb_store import ...` |
| `test_monitor.py` | `from data_manager.monitor import ...` | `from backend.data_manager.monitor import ...` |
| `test_tushare_provider.py` | `from data_manager.providers.tushare import ...` | `from backend.data_manager.providers.tushare import ...` |

### A4. `tests/test_simulator.py`

移除第 11-12 行的 `sys.path.insert`（该文件已使用 `from backend.simulator...`，只需清理 sys.path hack）。

### 验证

```bash
python -m pytest backend/data_manager/tests/ -v --tb=short
python -m pytest tests/test_simulator.py -v --tb=short
python -m pytest backend/tests/test_history.py -v --tb=short
# test_routes.py 暂时跳过（lifespan 问题在 Group E 处理）
```

---

## Group B：消除所有 bare `except:`（23 处，14 个文件）

将所有 `except:` 改为具体异常类型。以下是完整清单：

| 文件 | 行号 | 上下文 | 改为 |
|------|------|--------|------|
| `backend/engine/gain_predictor/predictor.py` | ~500 | 价格计算 | `except (ValueError, IndexError, ZeroDivisionError):` |
| `backend/engine/probability_predictor/predictor.py` | ~451 | 价格比较 | `except (ValueError, IndexError, ZeroDivisionError):` |
| `backend/data_manager/prediction_store.py` | ~46 | `ast.literal_eval` | `except (ValueError, SyntaxError):` |
| `backend/data_manager/fetcher.py` | ~786 | JSON 缓存读取 | `except (OSError, json.JSONDecodeError, KeyError):` |
| `backend/data_manager/manager.py` | ~113 | TTL 判断 | `except (ValueError, TypeError, OSError):` |
| `backend/data_manager/manager.py` | ~234 | 文件读取 | `except (OSError, json.JSONDecodeError):` |
| `backend/data_manager/manager.py` | ~277 | 临时文件替换 | `except OSError:` |
| `backend/data_manager/manager.py` | ~353 | tushare 初始化 | `except Exception:` |
| `backend/data_manager/cache.py` | ~156 | TTL 判断 | `except (ValueError, TypeError, OSError):` |
| `backend/data_manager/cache.py` | ~350 | 缓存有效性 | `except (ValueError, TypeError, OSError):` |
| `backend/data_manager/cache.py` | ~366 | 获取缓存年龄 | `except (ValueError, TypeError):` |
| `backend/data_manager/cache.py` | ~447 | 清理缓存文件 | `except OSError:` |
| `backend/data_manager/cache.py` | ~590 | 质量评分 | `except (ValueError, TypeError, KeyError):` |
| `backend/data_manager/cleaner.py` | ~118 | 日期判断 | `except (ValueError, TypeError):` |
| `backend/data_manager/cleaner.py` | ~395 | 质量评分 | `except (ValueError, TypeError):` |
| `backend/data_manager/cleanup.py` | ~117 | 锁文件 | `except (OSError, ValueError):` |
| `backend/data_manager/cleanup.py` | ~148 | 锁检查 | `except (OSError, ValueError):` |
| `backend/data_manager/cleanup.py` | ~162 | 状态文件 | `except (OSError, json.JSONDecodeError):` |
| `backend/data_manager/nightly_data/tasks/validate_data.py` | ~115 | EM 数据获取 | `except Exception:` |
| `backend/backtester/backtest.py` | ~551 | 日期解析 | `except (ValueError, TypeError):` |
| `backend/simulator/stats.py` | ~313 | 日期解析 | `except (ValueError, TypeError):` |
| `backend/data_manager/tests/test_duckdb_store.py` | ~56 | 临时文件清理 | `except OSError:` |
| `backend/data_manager/tests/test_backup.py` | ~45 | 临时文件清理 | `except OSError:` |
| `backend/data_manager/tests/test_adjuster.py` | ~29 | 临时文件清理 | `except OSError:` |

**注意**：上面的行号是近似值（基于当前代码扫描），请以实际 `except:` 位置为准。如果某处需要 `import json` 才能用 `json.JSONDecodeError`，请在文件顶部补上。

### 验证

```bash
# 确认没有遗漏
rg 'except\s*:' backend/ tests/ --glob '*.py'
```

预期：0 匹配。

---

## Group C：清理未使用导入（5 个文件）

| 文件 | 未使用导入 | 操作 |
|------|-----------|------|
| `backend/api/router.py` | `Optional`（from typing） | 从 typing import 中移除 `Optional`（**仅此修改，不动其他内容**） |
| `backend/api/websocket.py` | `import asyncio` | 删除该行 |
| `backend/engine/cp_engine/parallel.py` | `from functools import partial` | 删除该行 |
| `backend/tests/test_fusion.py` | `MagicMock`（from unittest.mock） | 从 import 中移除 `MagicMock` |
| `tests/backtester/test_optimizer_api.py` | `MagicMock` | 从 import 中移除 `MagicMock` |

### 验证

```bash
python -m pytest backend/tests/test_fusion.py -v
python -c "from backend.api.router import router"
python -c "from backend.api.websocket import ConnectionManager"
python -c "from backend.engine.cp_engine.parallel import parallel_process_stocks"
```

---

## Group D：依赖文件对齐

### D1. `backend/requirements.txt`

添加：
```
tushare>=1.4.0
```

移除（全项目无 `import sqlalchemy` 和 `import aiosqlite`）：
```
sqlalchemy>=2.0.36
aiosqlite>=0.20.0
```

### D2. 创建 `backend/requirements-dev.txt`

```
-r requirements.txt
pytest>=7.0
```

### 验证

```bash
# 确认 tushare 能找到使用处
rg 'import tushare' backend/
# 确认 sqlalchemy/aiosqlite 确实无使用
rg 'import sqlalchemy|import aiosqlite|from sqlalchemy|from aiosqlite' backend/ tests/
```

预期：tushare 有匹配，sqlalchemy/aiosqlite 无匹配。

---

## Group E：测试修复

### E1. `tests/test_simulator.py` — `test_can_buy_insufficient_cash`

该测试创建 `Account()` 但没有 mock 数据库，导致 `cash` 属性走真实 DB 路径返回默认值 20000，使 `can_buy(10, 100)` 返回 `True`。

修复方案：mock `Account.cash` 属性返回 0：

```python
def test_can_buy_insufficient_cash(self):
    """测试资金不足时无法买入"""
    from backend.simulator.account import Account
    from unittest.mock import PropertyMock

    account = Account.__new__(Account)  # 避免 __init__ 连接 DB
    with patch.object(type(account), 'cash', new_callable=PropertyMock, return_value=0):
        result, reason = account.can_buy(price=10.0, quantity=100)
        assert result == False
        assert "资金不足" in reason or "需要" in reason
```

或者更简单的方式：直接 mock `account.cash` 和 `account.calculate_freeze`。请根据 `Account` 的实际实现选择最简洁的方式。核心是确保测试不依赖真实 DB。

### E2. `backend/tests/test_routes.py` — 创建 conftest.py

创建 `backend/tests/conftest.py`，提供 mock lifespan 的 TestClient：

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """提供跳过重量级 lifespan 的 TestClient"""
    from contextlib import asynccontextmanager
    from fastapi import FastAPI

    @asynccontextmanager
    async def mock_lifespan(app):
        yield

    with patch('backend.api.main.lifespan', mock_lifespan):
        from backend.api.main import app
        with TestClient(app) as c:
            yield c
```

然后修改 `test_routes.py`：
- 移除模块级 `client = TestClient(app)`（已在 Group A 移除了 sys.path hack）
- 把所有测试类改为接收 `client` fixture 参数
- 保持所有原有测试逻辑不变

**注意**：mock lifespan 后，很多依赖初始化数据的测试可能会因为全局状态不存在而返回不同结果。对于那些需要真实数据的测试（如 `test_cp_top_score_ranges`），可以标记为 `@pytest.mark.integration`，本次不要求通过。只要 test_routes.py 能**被 pytest 收集和运行**（不再因 lifespan 超时而完全无法执行）就是成功。

### E3. 调整 `tests/backtester/test_optimizer_api.py` 的 skip 逻辑

当前 4 个测试因为 `importorskip("fastapi")` 和 `TestClient(app)` 失败而 skip。既然 Group A 已修复导入路径，确认这些测试是否能正常运行。如果仍因 lifespan 超时而 skip，接受现状并记录。

### 验证

```bash
python -m pytest tests/test_simulator.py -v --tb=short
python -m pytest backend/tests/test_routes.py -v --tb=short -x
python -m pytest backend/data_manager/tests/ -v --tb=short
python -m pytest backend/tests/ -v --tb=short --ignore=backend/tests/test_routes.py
python -m pytest tests/backtester/ -v --tb=short
```

---

## Group F：波动率管道修复

### F1. `backend/data_manager/filler.py` — 传递 `volatility_20d`

在 `_create_stock_cp()` 方法（约第 1796 行）中，在调用 `create_stock_from_raw()` 后，从 K 线数据计算并设置 `volatility_20d`：

```python
# 计算波动率
if len(klines) >= 20:
    closes = [k.get('close', 0) for k in klines]
    if closes and all(c > 0 for c in closes[-20:]):
        returns = []
        for i in range(1, min(20, len(closes))):
            if closes[-i-1] > 0:
                returns.append((closes[-i] - closes[-i-1]) / closes[-i-1])
        if returns:
            import numpy as np
            std = np.std(returns)
            stock.volatility_20d = std * np.sqrt(250) * 100  # 年化波动率 %
```

在 `stock = create_stock_from_raw(...)` 之后、`return stock` 之前添加。

**注意**：`filler.py` 已经 `import numpy as np`（在其他地方使用），确认后可直接使用。如果没有，在文件顶部添加导入。计算公式必须与 `backend/engine/probability_predictor/features.py:_calc_volatility` 保持一致（年化 %）。

### F2. `backend/recommender/buy_analyzer.py` — 修复波动率阈值

将第 242 行：
```python
if volatility > 8:
```
改为：
```python
if volatility > 40:
```

同时更新第 243 行的提示信息，将 `"偏高"` 的标准与年化 % 对齐。

### F3. `backend/recommender/prompts.py` — 同样修复

将波动率判断阈值从 `8` / `5` 调整为与年化波动率一致的合理值：
- `if volatility > 40:` → 偏高
- `elif volatility > 25:` → 适中

### 验证

```bash
python -m pytest backend/tests/test_fusion.py -v
python -c "from backend.recommender.buy_analyzer import BuyAnalyzer"
python -c "from backend.recommender.prompts import RecommendPromptBuilder"
```

---

## Group G：CI 修复

### G1. 修复 lint 步骤（永远不失败的假检查）

将 ci.yml 第 43-45 行：
```yaml
      - name: Run linter
        working-directory: ./frontend
        run: npm run lint || true
```

改为：
```yaml
      - name: Build check
        working-directory: ./frontend
        run: npx tsc --noEmit || true
```

这至少运行 TypeScript 类型检查。`|| true` 暂时保留（首次引入，避免阻塞 CI）。

### G2. 修复 api-health-check 假通过

将第 64-65 行：
```yaml
      - name: Check API
        run: curl -f http://127.0.0.1:8001/api/health || echo "API not responding"
```

改为：
```yaml
      - name: Check API
        run: |
          curl -f --retry 3 --retry-delay 5 http://127.0.0.1:8001/api/health
```

同时在 start backend 步骤添加 Python 版本：
```yaml
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
```

### G3. 扩展 CI 测试范围

在 backend-test job 的 pytest 命令中添加更多测试路径：

```yaml
      - name: Run backend tests
        run: |
          python -m pytest backend/tests/ tests/backtester/ backend/data_manager/tests/ tests/test_simulator.py -v --ignore=backend/tests/test_routes.py
```

暂时排除 `test_routes.py`（依赖 mock lifespan，CI 中可能行为不一致）。

### 验证

检查 YAML 语法：
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
```

---

## Group H：前端 Bug 修复

### H1. `frontend/src/shared/services/api.ts` — 回测 API 参数丢失（关键 Bug）

当前（第 88-93 行）：
```typescript
export const backtestApi = {
  runSimple: (params: BacktestParams): Promise<BacktestResult> =>
    request<BacktestResult>('/backtest/simple', {
      method: 'GET',
    }),
}
```

`params` 被接收但从未使用。后端 `/api/backtest/simple` 需要 `start_date`、`end_date`、`holding_days`、`top_n` 作为 query parameters。

修复为：
```typescript
export const backtestApi = {
  runSimple: (params: BacktestParams): Promise<BacktestResult> => {
    const searchParams = new URLSearchParams()
    if (params.start_date) searchParams.set('start_date', params.start_date)
    if (params.end_date) searchParams.set('end_date', params.end_date)
    if (params.holding_days) searchParams.set('holding_days', String(params.holding_days))
    if (params.top_n) searchParams.set('top_n', String(params.top_n))
    const query = searchParams.toString()
    return request<BacktestResult>(`/backtest/simple${query ? `?${query}` : ''}`)
  },
}
```

### H2. `frontend/src/shared/services/api.ts` — localStorage 安全解析

第 99-100 行：
```typescript
const stored = localStorage.getItem('watchlist_groups')
return Promise.resolve(stored ? JSON.parse(stored) : [])
```

改为：
```typescript
const stored = localStorage.getItem('watchlist_groups')
try {
  return Promise.resolve(stored ? JSON.parse(stored) : [])
} catch {
  return Promise.resolve([])
}
```

### 验证

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

---

## Group I：文档同步

### I1. `README.md`

- 更新"API 说明"中的错误路径：`/api/stock/{code}` → `/api/cp/stock/{code}`
- 更新"项目结构"中 `plan/` → `docs/plans/`
- 在"版本"说明处添加注释：详细战力公式见 `docs/plans/PROJECT_OVERVIEW.md`

### I2. `docs/plans/PROJECT_OVERVIEW.md`

- 前端状态：将"待实现"改为"v2.2 已实现基础模块（路由、战力、推荐、回测、模拟页面），工程化待完善"

### I3. `docs/README.md`

- 引擎版本：与 PROJECT_OVERVIEW 保持一致

### I4. `docs/plans/frontend/ISSUES.md`

- 替换"暂无问题"为当前实际问题列表（至少记录 backtest API 参数 bug）

### I5. `docs/superpowers/plans/PROJECT_FACT_BASE.md`

全面更新：
- 记录本次所有修复
- 更新测试基线（所有测试路径的 passed/failed/skipped）
- 更新已知冲突状态
- 更新后续优先任务建议

### 验证

```bash
# 检查文档中没有明显的过时路径
rg '/api/stock/' README.md docs/
```

---

## 不在本次范围的问题（记录到 PROJECT_FACT_BASE）

以下问题已发现但需要单独设计任务：

1. **硬编码路径统一**：20+ 个文件中 `DATA_DIR` 硬编码为 `/home/ailearn/projects/TradeSnake/...`。需要设计 config 模块后统一替换。
2. **前端 ESLint/Prettier 配置**：需要选择规则集、添加依赖、修复所有 lint 错误。单独任务。
3. **前端遗留 JSX 代码清理**：`frontend/src/pages/`、`frontend/src/components/`、`frontend/src/hooks/` 中有大量未被 `App.tsx` 引用的旧文件。需先确认是否完全废弃。
4. **前端无障碍（a11y）改进**：Header/SearchBar/Backtest 表单缺少 aria 属性。
5. **test_routes.py 的集成测试标记**：mock lifespan 后部分测试可能语义变化，需要标记 `@pytest.mark.integration`。
6. **缺失测试覆盖**：`backend/recommender/`（除 fusion）、`backend/stock_selector/`、`backend/models/`、`backend/api/websocket.py` 等模块无测试。

---

## 最终验证清单

所有 Group 完成后，执行以下命令并汇总结果：

```bash
# 1. 所有后端核心测试
python -m pytest backend/tests/ -v --tb=short --ignore=backend/tests/test_routes.py

# 2. data_manager 测试
python -m pytest backend/data_manager/tests/ -v --tb=short

# 3. backtester 测试
python -m pytest tests/backtester/ -v --tb=short

# 4. simulator 测试
python -m pytest tests/test_simulator.py -v --tb=short

# 5. test_routes.py（可能部分失败，记录结果）
python -m pytest backend/tests/test_routes.py -v --tb=short -x --timeout=120

# 6. bare except 检查
rg 'except\s*:' backend/ tests/ --glob '*.py'

# 7. 前端构建
cd frontend && npx tsc --noEmit 2>&1 | head -20; npm run build

# 8. CI YAML 语法
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

# 9. 改动范围
git diff --stat
```

---

## 报告格式

```
Summary
  按 Group 列出所有修改（A-I）

Verification
  9 项验证命令的输出摘要，每项标注 PASS/FAIL/PARTIAL

Files Modified
  完整的改动文件列表

Remaining Issues
  未能修复的问题（如 test_routes.py 部分测试因缺少数据失败）
  
Out of Scope (已记录)
  硬编码路径、前端 ESLint、遗留代码清理等

Next Task Recommendation
  后续优先任务排序
```
