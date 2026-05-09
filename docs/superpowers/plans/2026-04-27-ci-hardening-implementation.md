# 任务：CI 健壮化

> 日期：2026-04-27  
> 类型：Infrastructure（低风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：前端组件测试任务完成后执行（因为要加 `npm run test` 到 CI）

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

---

## Goal

让 CI pipeline 从"宽松模式"变为"严格可信赖"模式：

1. 移除 `|| true`：API contract tests 不再允许静默失败
2. 修复 api-health-check job 的超时问题
3. 添加前端测试到 CI（`npm run test`）
4. 确保整个 workflow 在本地可验证

完成后：所有 CI steps 要么通过要么失败（无掩盖），且每个 job 的设计意图清晰。

---

## Context

当前 `.github/workflows/ci.yml` 有三个问题：

### 问题 1：`|| true` 掩盖失败（第 29 行）

```yaml
- name: Run API contract tests
  run: |
    python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short || true
```

在上一轮 router 拆分后，25 个 non-integration route tests 已全部通过。`|| true` 不再需要。

### 问题 2：api-health-check 超时不合理

```yaml
- name: Start backend
  run: |
    pip install -r backend/requirements.txt -q
    timeout 30 python -c "from backend.api.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8001)" &
    sleep 10
```

项目实际启动时间约 60 秒（数据初始化）。`timeout 30` 会在启动完成前就杀掉进程。`sleep 10` 也远远不够。

有两个修复方案：
- **方案 A（推荐）**：改为导入验证（不启动 uvicorn，只验证 app 对象能创建）
- **方案 B**：增大 timeout 和 sleep（但 CI 环境下网络/数据不一定可用）

由于 CI 环境没有真实数据库文件（data/ 不在 repo 中），实际 uvicorn 启动大概率会因为找不到 DB 而最终失败。方案 A 更合理。

### 问题 3：前端缺少 test step

前端组件测试写完后，CI 应运行 `npm run test`。

---

## Scope

Allowed changes:

- `.github/workflows/ci.yml`

Out of scope:

- 任何 backend/ 或 frontend/ 代码
- 不添加新的 CI job（保持三个 job 结构）
- 不引入 Docker、服务容器或数据库 fixture

---

## Autonomy

Claude Code 可以自主决定：

- api-health-check job 的具体验证方式（导入测试 vs 配置验证 vs 启动参数）
- 是否将 api-health-check 重命名为更准确的名字
- step 的命名措辞

---

## Stop Conditions

- 移除 `|| true` 后发现 route tests 在无数据环境下确实会失败（需要先修测试）
- api-health-check 的替代方案需要修改后端代码

---

## Steps

### Step 1: 验证 contract tests 稳定性

- [ ] 本地运行 `python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short`
- [ ] 确认全部通过（无需 `|| true`）
- [ ] 如果有失败，停止并报告（回到 Cursor 评审）

### Step 2: 修改 CI YAML

- [ ] 移除第 29 行的 `|| true`
- [ ] 将 `api-health-check` job 改为纯导入验证模式：

```yaml
  api-import-check:
    name: API Import Check
    runs-on: ubuntu-latest
    container: python:3.11

    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: pip install -r backend/requirements.txt -q

      - name: Verify app import
        run: |
          python -c "from backend.api.main import app; print(f'Routes: {len(app.routes)}')"
          python -c "from backend.api.dependencies import cp_engine, db; print('Dependencies OK')"
          python -c "from backend.api.routers import cp, history, simulator, backtest, risk, prediction, system; print('All routers OK')"
```

- [ ] 在 frontend-build job 中添加 test step（在 lint 之后，build 之前）：

```yaml
      - name: Test
        working-directory: ./frontend
        run: npm run test
```

### Step 3: YAML 验证

- [ ] `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"`

### Step 4: 本地模拟 CI 各步骤

- [ ] 后端测试：`python -m pytest backend/tests/ tests/backtester/ backend/data_manager/tests/ tests/test_simulator.py -v -m "not integration" --ignore=backend/tests/test_routes.py`
- [ ] Contract tests：`python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short`
- [ ] 导入验证：`python -c "from backend.api.main import app; print(f'Routes: {len(app.routes)}')"` 
- [ ] 前端：`cd frontend && npm run typecheck && npm run lint && npm run test && npm run build`

---

## Verification

```bash
# YAML 语法
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"

# 后端测试（无 || true）
python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short

# 导入验证
python -c "from backend.api.main import app; print(f'Routes: {len(app.routes)}')"
python -c "from backend.api.dependencies import cp_engine, db; print('Dependencies OK')"

# 前端全流程
cd frontend && npm run test && npm run build
```

---

## 最终 CI YAML 期望结构

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  backend-test:
    name: Backend Tests
    runs-on: ubuntu-latest
    container: python:3.11
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest
      - name: Run backend tests
        run: |
          python -m pytest backend/tests/ tests/backtester/ backend/data_manager/tests/ tests/test_simulator.py -v -m "not integration" --ignore=backend/tests/test_routes.py
      - name: Run API contract tests
        run: |
          python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short

  frontend-build:
    name: Frontend Build & Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
      - name: Install dependencies
        working-directory: ./frontend
        run: npm ci
      - name: TypeScript check
        working-directory: ./frontend
        run: npm run typecheck
      - name: Lint
        working-directory: ./frontend
        run: npm run lint
      - name: Test
        working-directory: ./frontend
        run: npm run test
      - name: Build
        working-directory: ./frontend
        run: npm run build

  api-import-check:
    name: API Import Check
    runs-on: ubuntu-latest
    container: python:3.11
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: pip install -r backend/requirements.txt -q
      - name: Verify app structure
        run: |
          python -c "from backend.api.main import app; print(f'Routes: {len(app.routes)}')"
          python -c "from backend.api.dependencies import cp_engine, db; print('Dependencies OK')"
          python -c "from backend.api.routers import cp, history, simulator, backtest, risk, prediction, system; print('All routers OK')"
```

---

## Completion Report Format

```markdown
## Summary
- 修改内容

## Verification
- 每项本地验证结果

## CI Structure
- 最终 3 个 job 的功能说明

## Remaining Issues
- 如有

## Next Task Recommendation
- 后续建议
```
