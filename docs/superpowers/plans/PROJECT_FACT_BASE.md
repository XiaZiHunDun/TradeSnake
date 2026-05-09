# TradeSnake Project Fact Base

> 日期：2026-04-27
> 用途：给 Cursor 设计/评审代理与 Claude Code 执行代理提供当前项目事实基线。
> 原则：这里记录的是"执行任务时应先采用的事实"，不是永久产品规范。若代码、测试或用户指令发生变化，应同步更新本文件。

---

## 一、项目定位

TradeSnake（股市贪吃蛇）把股票市场重新解释为战力系统，用"战力值"替代纯资金视角来评估股票、组合、换股和回测表现。

当前产品边界以 `docs/plans/PROJECT_OVERVIEW.md` 为准：

- 主流程股票池、战力主算路径、批量行情抽样以沪深主板为边界。
- 创业板、科创板、北交所不按与主板同等能力扩展。
- 数据源层可能拉取全市场列表，但"全市场数据源"不等于产品能力覆盖全市场。

---

## 二、技术栈

### 2.1 后端

- 语言：Python。
- 框架：FastAPI + uvicorn。
- 限流：代码使用 `slowapi`。
- 数据相关：pandas、akshare、requests、SQLAlchemy、aiosqlite，代码中还使用 DuckDB/SQLite 存储能力。
- 依赖文件：`backend/requirements.txt`。
- 主要 API 入口：`backend/api/main.py`。
- 路由聚合：`backend/api/router.py`。
- **集中配置**：`backend/config.py` 定义所有文件系统路径，支持 `TRADESNAKE_DATA_DIR` 环境变量覆盖。15+ 后端文件已迁移为 `from backend.config import ...`。

### 2.2 前端

- 构建：Vite。
- 框架：React 18。
- 样式：Tailwind CSS。
- 路由：react-router-dom。
- 数据请求：fetch + `@tanstack/react-query`。
- 状态：zustand。
- 入口：`frontend/src/main.jsx`。
- 路由壳层：`frontend/src/App.tsx`。
- API 封装：`frontend/src/shared/services/api.ts`。
- 代码质量：ESLint + Prettier + Vitest 已配置。
- Scripts：`dev` / `build` / `preview` / `lint` / `format` / `typecheck` / `test` / `test:watch`。

---

## 三、主要目录

```text
TradeSnake/
├── backend/
│   ├── api/                 # FastAPI 应用和路由
│   ├── data_manager/        # 数据获取、缓存、存储、夜间任务
│   ├── stock_selector/      # 股票筛选和池管理
│   ├── engine/              # 战力、涨幅、概率预测
│   ├── recommender/         # 推荐、融合、买卖分析
│   ├── simulator/           # 模拟账户、持仓、交易
│   ├── backtester/          # 回测、策略、指标、优化
│   ├── models/              # Pydantic 等模型
│   ├── config.py            # 集中式路径配置
│   └── tests/               # CI 当前覆盖的后端测试
├── frontend/                # React/Vite 前端
├── tests/                   # 根目录测试，含 backtester 测试
├── docs/
│   ├── plans/               # 项目和模块架构文档
│   ├── references/          # 旧版设计和参考材料
│   ├── reviews/             # 外部或历史评审意见
│   └── superpowers/         # Cursor/Claude Code 设计与执行任务
└── data/                    # 本地数据与缓存
```

---

## 四、文档事实源优先级

默认优先级：

1. 当前代码与实际可运行测试。
2. 最新日期的 `docs/superpowers/specs` 与 `docs/superpowers/plans`。
3. `docs/plans/PROJECT_OVERVIEW.md` 和模块架构文档。
4. 根目录 `README.md`。
5. `docs/references` 与较旧评审文档。

当前建议：

- 产品范围优先看 `docs/plans/PROJECT_OVERVIEW.md`。
- 新的执行任务优先放在 `docs/superpowers/plans`。
- 新的设计说明优先放在 `docs/superpowers/specs`。
- 根目录 `README.md` 可作为快速介绍，但不应作为唯一事实源。

---

## 五、已知冲突与风险

### 5.1 README 与项目概览版本不一致

- `README.md` 描述战力公式为 v18 综合版。
- `docs/plans/PROJECT_OVERVIEW.md` 描述项目为 v19.9.9，并记录 v19.6+ 战力公式。
- 执行任务时，涉及战力公式和产品边界应优先使用 `PROJECT_OVERVIEW.md` 与当前代码。

### 5.2 后端启动命令存在导入路径冲突风险

- ~~`README.md` 写法是 `cd backend && python -m uvicorn api.main:app --reload --port 8001`~~ ✅ 已修复：统一为从项目根目录运行 `python -m uvicorn backend.api.main:app`
- 代码中大量使用 `from backend...` 导入（跨模块超过 140 处）。
- 当前标准启动方式：`python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001`
- README、CI、任务文档已同步为此方式。

### 5.3 CI 与依赖文件不完全一致

- ~~`.github/workflows/ci.yml` 手动安装 `fastapi uvicorn akshare pandas requests slowapi pytest`~~ ✅ 已修复：CI 现在使用 `pip install -r backend/requirements.txt`
- ~~`backend/requirements.txt` 未列出 `slowapi`~~ ✅ 已修复：requirements.txt 现已补齐 slowapi, numpy, scipy, baostock, duckdb
- 代码 `backend/api/main.py` 直接导入 `slowapi`。

### 5.4 测试范围统一

- ~~CI 当前运行 `python -m pytest backend/tests/ -v`~~ ✅ 已修复：CI 现在同时覆盖 `backend/tests/`、`tests/backtester/`、`backend/data_manager/tests/`、`tests/test_simulator.py`
- 测试基线（2026-04-27）：
  - `backend/tests/`（不含 test_routes.py 因 lifespan mock）：**80 passed**
  - `backend/data_manager/tests/`：**~170 passed**
  - `tests/backtester/`：**48 passed**
  - `tests/test_simulator.py`：**5 passed**
  - `backend/tests/test_routes.py`（非 integration）：**25 passed**（7 integration deselected）
  - 总计：**250+ passed, 1 skipped**
- `pyproject.toml` 已创建（pythonpath + integration marker + testpaths）

### 5.5 前端工程化 ✅ 已完成

- ~~`frontend/package.json` 只有 `dev`、`build`、`preview`~~ ✅ 已修复：已添加 `lint` / `format` / `typecheck` / `test` / `test:watch`
- ~~CI 中执行 `npm run lint || true`，但 package.json 未定义 lint`~~ ✅ 已修复：CI 现在分别执行 `npm run typecheck` 和 `npm run lint`
- ~~`frontend/src/utils/__tests__/export.test.js` 使用 Jest 风格~~ ✅ 已删除该文件
- Vitest 已配置（`vitest.config.ts` + `src/test-setup.ts`）
- 0 个前端测试文件（基础设施已就绪，待编写测试）

### 5.6 前端状态文档过时

- `docs/plans/PROJECT_OVERVIEW.md` 中前端状态写为"方案已完成，待实现"。
- 实际 `frontend/src/App.tsx` 已有 v2.2 路由和模块页面。
- 后续文档同步任务应明确"已有 v2.2 实现，但仍可能待重构或补齐工程化"。

### 5.7 当前工作树有既有改动

截至本文件创建前的检查：

- 当前分支：`master`，相对 `origin/master` ahead 28。
- 已有未提交改动：`backend/api/router.py`。
- 当前协作体系任务不应修改 `backend/api/router.py`。

---

## 六、运行与验证命令候选

这些命令需要在后续任务中按实际环境验证。

### 6.1 后端

标准启动命令（已统一）：

```bash
conda activate tradesnake
python -m uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8001
```

> 从项目根目录运行，不要 `cd backend`。启动约需60秒（数据初始化）。

### 6.2 后端测试

CI 当前命令：

```bash
python -m pytest backend/tests/ tests/backtester/ backend/data_manager/tests/ tests/test_simulator.py -v -m "not integration" --ignore=backend/tests/test_routes.py
python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short || true
```

回测优化相关命令候选：

```bash
python -m pytest tests/backtester/ -v
```

### 6.3 前端

开发：

```bash
cd frontend
npm run dev
```

构建：

```bash
cd frontend
npm run build
```

类型检查：

```bash
cd frontend
npm run typecheck
```

Lint：

```bash
cd frontend
npm run lint
```

测试：

```bash
cd frontend
npm run test
```

---

## 七、Claude Code 执行默认规则

Claude Code 拿到 TradeSnake 任务时应默认：

- 先读本文件和任务文件。
- 先检查 `git status --short`，识别并保护用户已有改动。
- 优先使用现有模块边界和局部 helper。
- 不扩大产品范围，不擅自改变数据口径。
- 对文档冲突做最小同步，并在结果中报告。
- 每个任务结束前运行任务要求的验证命令。

Claude Code 只有在以下场景停下询问：

- 产品边界、战力公式、交易费用、回测标准或数据源优先级需要改动。
- 需要外部凭据、付费服务、部署资源或新基础设施。
- 需要删除数据、迁移持久化格式或破坏公开 API。
- 任务说明互相矛盾且无法安全解释。
- 大面积测试失败且无法判断原因。

---

## 八、后续优先任务建议

建议按以下顺序拆分后续执行任务：

1. 统一后端运行命令、README 与 CI 的导入路径。
2. 对齐后端依赖文件与 CI 依赖，补齐 `slowapi` 等直接依赖。
3. 明确 `backend/tests` 与 `tests/backtester` 的测试分层和 CI 覆盖范围。
4. 同步前端状态文档，明确 v2.2 已实现范围与待补齐工程化。
5. 编写前端组件测试（Vitest 基础设施已就绪）。
