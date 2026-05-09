# 任务：配置模块统一 + 前端工程化 + 测试基础设施完善

> 日期：2026-04-27  
> 类型：Architecture + Engineering（跨模块改进）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：`2026-04-27-project-wide-quality-sweep-implementation.md`（已完成）

---

## 目标

三个独立的大改进，一次性完成：

1. **Part 1**：创建集中式配置模块，消除 15+ 个文件中的硬编码路径
2. **Part 2**：清理前端死代码、修复类型问题、添加 ESLint + Vitest
3. **Part 3**：修复 test_routes.py 路由不匹配、创建 pytest 基础设施

完成后：后端路径全部可配置、前端工程化达标、测试套件路由与实际 API 一致。

---

## 执行原则

- **自主执行全部步骤**，不需要中途询问用户。
- 三个 Part 相互独立，按顺序完成。每个 Part 完成后运行验证。
- 如果遇到无法解决的依赖（如 npm 安装失败），跳过并记录，继续其他 Part。
- 保护已有的 `backend/api/router.py` 用户未提交改动（不修改 router.py 的业务逻辑）。

---

# Part 1：集中式配置模块

## 设计

创建 `backend/config.py`，集中定义所有文件系统路径，支持环境变量覆盖。

### `backend/config.py` 结构

```python
"""
TradeSnake 集中式路径配置
所有文件系统路径从此模块获取，支持环境变量覆盖。
"""
import os
from pathlib import Path

# 项目根目录：从 config.py 所在位置向上推导
# backend/config.py → backend/ → TradeSnake/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 数据根目录（支持 TRADESNAKE_DATA_DIR 环境变量覆盖）
DATA_DIR = Path(os.environ.get('TRADESNAKE_DATA_DIR', str(PROJECT_ROOT / 'data')))

# === 数据库路径 ===
SQLITE_PATH = DATA_DIR / 'tradesnake.db'
DUCKDB_PATH = DATA_DIR / 'historical.duckdb'
PREDICTION_DB_PATH = DATA_DIR / 'tradesnake_prediction.db'
CP_HISTORY_DB_PATH = DATA_DIR / 'tradesnake_cp_history.db'
NIGHTLY_STATE_DB_PATH = DATA_DIR / 'nightly_state.db'
BACKTEST_REPORTS_DB_PATH = DATA_DIR / 'backtest_reports.db'
SIMULATOR_DB_PATH = DATA_DIR / 'simulator.db'

# === 目录 ===
BACKUP_DIR = DATA_DIR / 'backup'
LOG_DIR = PROJECT_ROOT / 'logs' / 'nightly'
CACHE_DIR = DATA_DIR  # JSON 缓存文件在 data/ 下

# === CP 历史 JSON 回退 ===
HISTORY_DIR = DATA_DIR
HISTORY_FILE = HISTORY_DIR / 'cp_history.json'

# === API 状态文件 ===
REFRESH_STATE_FILE = DATA_DIR / '.refresh_state.json'
```

### 替换清单

以下文件需要把硬编码的 `DATA_DIR = Path("/home/ailearn/...")` 替换为 `from backend.config import ...`。

**每个文件的具体替换**：

| 文件 | 删除/替换 | 导入 |
|------|----------|------|
| `backend/api/main.py` (行 23) | 删除 `DATA_DIR = Path("/home/ailearn/...")` | `from backend.config import DATA_DIR, SQLITE_PATH, REFRESH_STATE_FILE` |
| `backend/api/main.py` (行 142) | 删除 `DB_PATH = "/home/ailearn/..."` | 使用已导入的 `SQLITE_PATH` |
| `backend/api/main.py` (行 ~740) | 删除 `sqlite_path = Path("/home/ailearn/...")` | 使用已导入的 `SQLITE_PATH` |
| `backend/api/main.py` (行 ~220) | 删除 `_STATE_FILE = DATA_DIR / ".refresh_state.json"` | 使用 `REFRESH_STATE_FILE` |
| `backend/data_manager/fetcher.py` (行 34) | 删除 `CACHE_DIR = "/home/ailearn/..."` | `from backend.config import CACHE_DIR` |
| `backend/data_manager/manager.py` (行 58) | 删除 `DATA_DIR = Path("/home/ailearn/...")` | `from backend.config import DATA_DIR` |
| `backend/data_manager/cache.py` (行 23) | 删除 `DATA_DIR = ...` | `from backend.config import DATA_DIR` |
| `backend/data_manager/filler.py` (行 77-78) | 删除 `DATA_DIR` 和 `DB_PATH` | `from backend.config import DATA_DIR, SQLITE_PATH` |
| `backend/data_manager/cleanup.py` (行 31-34) | 删除 `DATA_DIR`, `BACKUP_DIR`, `SQLITE_PATH`, `DUCKDB_PATH` | `from backend.config import DATA_DIR, BACKUP_DIR, SQLITE_PATH, DUCKDB_PATH` |
| `backend/data_manager/duckdb_store.py` (行 37-39) | 删除 `DATA_DIR`, `DUCKDB_PATH`, `SQLITE_PATH` | `from backend.config import DATA_DIR, DUCKDB_PATH, SQLITE_PATH` |
| `backend/data_manager/duckdb_store.py` (行 ~1203) | 删除内联硬编码 `Path(".../tradesnake.db")` | 使用已导入的 `SQLITE_PATH` |
| `backend/data_manager/pool_state_store.py` (行 29-30) | 删除 `DATA_DIR`, `SQLITE_PATH` | `from backend.config import SQLITE_PATH` |
| `backend/data_manager/prediction_store.py` (行 ~70) | 删除默认 `db_path` 硬编码字符串 | `from backend.config import PREDICTION_DB_PATH`，用作默认值 |
| `backend/data_manager/cp_history_store.py` (行 ~39) | 删除默认 `db_path` | `from backend.config import CP_HISTORY_DB_PATH` |
| `backend/data_manager/backup.py` (行 30-32) | 删除 `DATA_DIR`, `BACKUP_DIR` | `from backend.config import DATA_DIR, BACKUP_DIR, SQLITE_PATH` |
| `backend/data_manager/adjuster.py` (行 27-28) | 删除 `DATA_DIR`, `DB_PATH` | `from backend.config import SQLITE_PATH as DB_PATH` 或直接用 `SQLITE_PATH` |
| `backend/data_manager/nightly_data/state_manager.py` (行 7-8) | 删除 `DATA_DIR`, `STATE_DB` | `from backend.config import NIGHTLY_STATE_DB_PATH as STATE_DB` |
| `backend/data_manager/nightly_data/logger.py` (行 7-8) | 删除 `LOG_DIR` | `from backend.config import LOG_DIR` |
| `backend/engine/cp_engine/history.py` (行 33-34) | 删除 `HISTORY_DIR`, `HISTORY_FILE` | `from backend.config import HISTORY_DIR, HISTORY_FILE` |
| `backend/simulator/database.py` (行 13) | 删除 `DB_PATH` | `from backend.config import SIMULATOR_DB_PATH as DB_PATH`（注意：simulator 可能用不同的 DB 文件，检查实际值） |
| `backend/backtester/verification.py` (行 ~683) | 修改默认 `db_path` | `from backend.config import BACKTEST_REPORTS_DB_PATH` |

**注意事项**：
- `simulator/database.py` 的 `DB_PATH` 可能指向不同的 SQLite 文件（如 `simulator.db`），检查实际硬编码值后决定对应的 config 变量
- 部分文件的 `DB_PATH` 只是 `DATA_DIR / "tradesnake.db"` 的别名，统一用 `SQLITE_PATH`
- `prediction_store.py` 和 `cp_history_store.py` 的构造函数接受 `db_path` 参数，改默认值即可
- 不修改 `scripts/` 和 `run_*.py` 中的路径（这些顶级脚本可以保持自己的路径解析逻辑）
- 不修改 `docs/` 中的示例路径

### 验证

```bash
# 1. 确认导入能工作
python -c "from backend.config import DATA_DIR, SQLITE_PATH, DUCKDB_PATH; print(f'DATA_DIR={DATA_DIR}'); print(f'SQLITE={SQLITE_PATH}')"

# 2. 确认所有后端模块能正常导入
python -c "from backend.api.main import app; print('main OK')"
python -c "from backend.data_manager.manager import get_data_manager; print('manager OK')"
python -c "from backend.data_manager.duckdb_store import get_duckdb_store; print('duckdb OK')"

# 3. 确认硬编码路径已清除（backend/ 下不含 /home/ailearn，排除 config.py 本身）
rg '/home/ailearn' backend/ --glob '*.py' --glob '!*config.py'

# 4. 运行测试
python -m pytest backend/tests/ -v --tb=short --ignore=backend/tests/test_routes.py
python -m pytest backend/data_manager/tests/ -v --tb=short
```

---

# Part 2：前端清理与工程化

## 2A. 删除死代码（26 个文件）

以下文件 **全部** 未被 `App.tsx` → `modules/` → `shared/` 导入链引用，是 v18 到 v19 迁移后的遗留物。

**删除 `frontend/src/pages/`**（整个目录，9 个文件）：
- Backtest.jsx, CPTopList.jsx, PersonalCP.jsx, PortfolioSimulator.jsx, RankingChanges.jsx, Recommend.jsx, SectorAnalysis.jsx, SingleStock.jsx, TradingCenter.jsx

**删除 `frontend/src/components/`**（整个目录，8 个文件）：
- DataSourceInfo.jsx, ErrorBoundary.jsx, FormulaEducation.jsx, Header.jsx, NotificationCenter.jsx, Skeleton.jsx, StockNews.jsx, StockScreener.jsx, TourGuide.jsx

**删除 `frontend/src/hooks/`**（整个目录，7 个文件）：
- useAccount.js, useHoldings.js, useNotification.jsx, useSettings.jsx, useTheme.jsx, useToast.jsx, useWatchlist.js

**删除 `frontend/src/utils/export.js`** 和 **`frontend/src/utils/__tests__/export.test.js`**（仅被死代码引用）。

**不删除** `frontend/src/utils/` 目录本身（可能有其他文件）。

### 验证

```bash
cd frontend && npm run build
```

构建应该成功，且 bundle 变小。

## 2B. 清理 package.json 中仅被死代码使用的依赖

以下依赖仅在已删除的 `.jsx` 文件中使用：

- `echarts` — 仅在死代码 `.jsx` 中使用
- `echarts-for-react` — 同上
- `lucide-react` — 同上
- `xlsx` — 仅在已删除的 `export.js` 中使用

```bash
cd frontend && npm uninstall echarts echarts-for-react lucide-react xlsx
```

同时清理 `vite.config.js` 中的 `manualChunks` 配置（如果引用了这些包）。

### 验证

```bash
cd frontend && npm run build
```

## 2C. 修复 TypeScript 类型问题

**`frontend/src/shared/types/index.ts`**：`TradeResult` interface 定义了两次（行 ~141 和 ~173），TypeScript 会合并它们但语义不同。

修复：保留完整版（包含交易详情的那个），删除简化版或重命名为 `TradeResponse`。根据实际使用情况决定（检查 `useApi.ts` 和 `api.ts` 中哪些地方使用 `TradeResult`）。

## 2D. 添加 ESLint + Prettier

```bash
cd frontend
npm install -D eslint @eslint/js typescript-eslint eslint-plugin-react-hooks eslint-plugin-react-refresh
npm install -D prettier
```

创建 `frontend/eslint.config.js`（ESLint 9 flat config）：

```javascript
import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

export default tseslint.config(
  { ignores: ['dist'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
)
```

创建 `frontend/.prettierrc`：

```json
{
  "semi": false,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "tabWidth": 2
}
```

更新 `frontend/package.json` scripts：

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint src",
    "format": "prettier --write src",
    "typecheck": "tsc --noEmit"
  }
}
```

运行 `npm run lint` 查看结果。修复能自动修的错误（`npx eslint src --fix`），其余仅记录数量不强制修为 0。

## 2E. 添加 Vitest（基础设施）

```bash
cd frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

在 `frontend/vite.config.js` 中添加 test 配置（或创建 `vitest.config.ts`）：

```javascript
// 在 vite.config.js 的 defineConfig 中添加
test: {
  environment: 'jsdom',
  globals: true,
  setupFiles: ['./src/test-setup.ts'],
}
```

创建 `frontend/src/test-setup.ts`：

```typescript
import '@testing-library/jest-dom'
```

更新 `frontend/package.json` scripts 添加：

```json
"test": "vitest run",
"test:watch": "vitest"
```

暂不迁移旧的 export.test.js（已删除），后续可以为现有组件添加测试。

### Part 2 综合验证

```bash
cd frontend
npm run build      # 构建成功
npm run lint       # 能运行（可有 warnings）
npm run typecheck  # 类型检查通过
npm run test       # vitest 运行（0 tests 也算通过）
```

---

# Part 3：测试基础设施完善

## 3A. 创建 `pyproject.toml`（pytest 配置）

在项目根目录创建 `pyproject.toml`：

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
markers = [
    "integration: tests requiring real data, database, or network (deselect with '-m \"not integration\"')",
]
testpaths = [
    "backend/tests",
    "backend/data_manager/tests",
    "tests",
]
```

## 3B. 创建 `backend/tests/conftest.py`

当前 `test_routes.py` 在模块级做了 mock lifespan + `TestClient(app)` 的创建。这种方式有效但不规范。

创建 `backend/tests/conftest.py`：

```python
import pytest


def pytest_configure(config):
    """注册自定义 markers"""
    config.addinivalue_line("markers", "integration: requires real data or network")
```

**注意**：不要把 test_routes.py 的 client 创建移到 conftest，因为它的 mock lifespan 逻辑是特殊的模块级 patch。保持现状即可。

## 3C. 修复 `test_routes.py` 路由不匹配

当前 `test_routes.py` 有大量路由路径与实际 `router.py` 不一致。以下是需要修改的测试：

### 3C-1. 修复路径错误的测试

| 测试 | 当前路径 | 正确路径 | 操作 |
|------|---------|---------|------|
| `TestStockEndpoint.test_stock_not_found` | `/api/stock/INVALID` | `/api/cp/stock/INVALID` | 修改路径 |
| `TestHistoryEndpoints.test_history_rankings_top` | `/api/history/rankings/top?days=30` | `/api/history/rankings?days=30&limit=10` | 修改路径和参数 |

### 3C-2. 删除不存在路由的测试

以下测试对应的 API 路由在当前 `router.py` 中**不存在**（已被移除或从未实现）：

**删除整个 `TestRiskStatsEndpoint` 类**（2 个测试）— `/api/stats/risk` 不存在。

**删除整个 `TestBatchStocksEndpoint` 类**（4 个测试）— `/api/stocks/batch` 不存在。

**删除整个 `TestTradeEndpoints` 类**（5 个测试）— `/api/trade/cost`、`/api/trade/cash_cost`、`/api/trade/cp_threshold` 不存在。

**删除 `TestHistoryEndpoints.test_history_rankings_changes`** — `/api/history/rankings/changes` 不存在。

### 3C-3. 修复响应断言不匹配的测试

**`TestRefreshEndpoint`**（6 个测试）：当前 mock lifespan 下，`/api/refresh` 会因 `get_stock_selector()` 或 `get_data_manager()` 未完整初始化而失败。将这些测试全部标记为 `@pytest.mark.integration`：

```python
@pytest.mark.integration
class TestRefreshEndpoint:
    ...
```

**`TestRecommendEndpoint.test_recommend_invalid_category`**：当前断言 `status_code == 400` 和中文错误消息，但 FastAPI Query validation 返回 422。修复为：

```python
def test_recommend_invalid_category(self):
    response = client.get("/api/cp/recommend?category=invalid")
    assert response.status_code == 422
```

**`TestRecommendEndpoint.test_recommend_allround`**：`allround` 不在当前 category pattern `^(value|growth|momentum|quality)$` 中。检查 router.py 确认后：如果确实不支持 `allround`，删除此测试或改为测试 422。

### 3C-4. 标记集成测试

以下测试依赖真实数据才有意义，标记为 `@pytest.mark.integration`：

```python
@pytest.mark.integration
class TestRefreshEndpoint:
    ...

# 在 TestCPEndpoints 中：
@pytest.mark.integration
def test_cp_top_score_ranges(self):
    ...
```

### 验证

```bash
# 不跑 integration 测试
python -m pytest backend/tests/test_routes.py -v --tb=short -m "not integration"

# 跑全部（部分可能失败）
python -m pytest backend/tests/test_routes.py -v --tb=short
```

## 3D. 修复 `test_backup_cache_json_nonexistent`

文件：`backend/data_manager/tests/test_backup.py`

当前测试用默认 `DATA_DIR`（真实目录），但该目录可能有 `.json` 文件导致测试通过而断言 `success == False` 失败。

修复：传入一个空临时目录：

```python
def test_backup_cache_json_nonexistent(self):
    """测试备份空目录（无 JSON 缓存文件）"""
    import tempfile
    with tempfile.TemporaryDirectory() as empty_dir:
        result = self.manager.backup_cache_json(data_dir=Path(empty_dir))
        assert result.success == False
```

### 验证

```bash
python -m pytest backend/data_manager/tests/test_backup.py -v --tb=short
```

## 3E. 更新 CI

更新 `.github/workflows/ci.yml` 的 backend-test 步骤：

```yaml
      - name: Run backend tests
        run: |
          python -m pytest backend/tests/ tests/backtester/ backend/data_manager/tests/ tests/test_simulator.py -v -m "not integration" --ignore=backend/tests/test_routes.py
```

同时添加 test_routes.py 的非集成测试：

```yaml
      - name: Run API contract tests
        run: |
          python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short || true
```

`|| true` 暂时保留，因为 mock lifespan 下部分测试可能仍有问题。

---

# 最终验证清单

所有 Part 完成后：

```bash
# Part 1
python -c "from backend.config import DATA_DIR; print(DATA_DIR)"
rg '/home/ailearn' backend/ --glob '*.py' --glob '!**/config.py'
python -m pytest backend/tests/ -v --tb=short --ignore=backend/tests/test_routes.py
python -m pytest backend/data_manager/tests/ -v --tb=short

# Part 2
cd frontend && npm run build && npm run lint && npm run typecheck

# Part 3
python -m pytest backend/tests/test_routes.py -v --tb=short -m "not integration"
python -m pytest backend/data_manager/tests/test_backup.py::TestBackupManager::test_backup_cache_json_nonexistent -v

# 全面
python -m pytest backend/tests/ tests/backtester/ backend/data_manager/tests/ tests/test_simulator.py -v -m "not integration" --ignore=backend/tests/test_routes.py
git diff --stat
```

---

# 报告格式

```
Summary
  按 Part 列出所有修改

Verification
  每项验证的输出

Files Created
  backend/config.py, pyproject.toml, conftest.py, eslint.config.js, .prettierrc, test-setup.ts, ...

Files Modified
  列表

Files Deleted
  前端删除的 26+ 个文件

Remaining Issues
  未能修复的问题

Next Task Recommendation
  后续建议
```

---

# 不在本次范围

1. `scripts/` 和 `run_*.py` 中的路径（这些顶层脚本可以后续统一）
2. `docs/` 中的示例路径（文档路径不影响运行时）
3. 前端组件测试编写（本次只建基础设施）
4. 补齐 recommender/stock_selector/models/websocket 的测试覆盖
5. test_routes.py 中 integration 测试的 fixture 编写
