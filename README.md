# TradeSnake - 股市贪吃蛇

将股票市场重新诠释为一场贪吃蛇游戏，用"战力值"替代金钱衡量股票价值。

## 项目概述

TradeSnake（股市贪吃蛇）将股市比作贪吃蛇游戏，核心理念是重新构建股票价值体系，不以金钱衡量，而是用"战力值"等新单位衡量股票价值。通过置换、低价值换高价值来提升自身价值。

**说明（产品范围）**：当前仓库内股票池、战力主算与批量行情抽样以 **沪深主板** 为边界；细节见 `docs/plans/PROJECT_OVERVIEW.md`「产品范围」。

## 技术栈

- **后端**: Python FastAPI
- **前端**: React + Vite + TailwindCSS + ECharts
- **数据源**: 东方财富数据中心API

## 战力公式 (v18 综合版)

```
总战力 = (成长分×40% + 价值分×40% + 动量分×20%) × 风险调整因子
```

> ⚠️ 战力公式已升级到 v18，采用更简洁的权重分配

### 因子计算

**成长分(40%)**: 净利润增长(0-300%)×0.6 + 营收增长(-50%-100%)×0.4

**价值分(40%)**: ROE（负值当0，ROE>25%截断）

**动量分(20%)**: 当日涨跌幅（限制在-10到10之间）

> ⚠️ v18 公式简化了质量分，将其整合到成长和价值中

### 风险评估（风险调整因子）

风险分数（0-100，越高风险越大）:

- **PE风险**: 亏损(30分) / PE>100(20分) / PE>50(10分) / PE<5(5分)
- **ROE风险**: ROE<0(25分) / ROE<5(10分)
- **增长风险**: 净利润下降<-50%(15分) / 净利润下降<0(5分)
- **波动风险**: 涨跌幅>8%(15分) / 涨跌幅>5%(8分)

**最终战力 = 基础战力 × (1 - 风险比例×10%)**

### 赚钱逻辑

- **价值型**: 高ROE + 低PE + 正增长
- **成长型**: 高增长 + 中等ROE
- **趋势型**: 高动量 + 正增长
- **质量型**: 高现金流 + 高毛利 + 低负债

## 功能模块

- [x] 战力榜单页面
- [x] 单股查询页面
- [x] 个人战力面板（持仓管理）
- [x] 智能推荐（价值型/成长型/趋势型/质量型/综合型）
- [x] 历史战力记录
- [x] 榜单变化追踪
- [x] 行业分析
- [x] 高级筛选器
- [x] 风险评估
- [x] 数据导出（CSV/JSON/Excel）
- [x] 通知中心
- [x] 调仓建议

## 运行

### 后端
```bash
conda activate tradesnake
cd backend
python -m uvicorn api.main:app --reload --port 8001
```

### 前端
```bash
cd frontend
npm install
npm run dev
```

## API端点

### 核心API
- `GET /api/cp/top?limit=200` - 获取战力榜
- `GET /api/cp/bottom?limit=10` - 获取避雷区
- `GET /api/stock/{code}` - 获取单只股票详情
- `POST /api/refresh?limit=200` - 手动刷新数据（限流: 5次/分钟）

### 推荐API
- `GET /api/cp/recommend?category=value|growth|momentum|quality|allround` - 获取推荐股票（已应用用户约束过滤）

### 用户配置API
- `GET /api/user/profile` - 获取用户配置（资金、板块、风险偏好、股息考虑）
- `PUT /api/user/profile` - 更新用户配置

> ⚠️ 推荐股票已自动过滤：只显示用户可交易板块、可承受价格范围内的股票

### 统计API
- `GET /api/stats/market` - 市场统计（含风险统计）
- `GET /api/stats/risk` - 风险统计详情

### 历史API
- `GET /api/history/changes?days=7` - 战力变化
- `GET /api/history/{code}?days=30` - 单只股票历史
- `GET /api/history/rankings/top?days=30` - 历史TOP10
- `GET /api/history/rankings/changes?days=30` - 榜单变化

### 批量API
- `POST /api/stocks/batch` - 批量获取股票

## 快捷键

| 按键 | 功能 |
|------|------|
| 1 | 战力榜单 |
| 2 | 单股查询 |
| 3 | 我的战力 |
| 4 | 智能推荐 |
| 5 | 组合模拟器 |
| 6 | 榜单变化 |
| 7 | 行业分析 |
| R | 刷新数据 |
| S | 打开设置 |
| T | 切换主题 |
| E | 打开战法学堂 |
| D | 打开数据说明 |
| ESC | 关闭弹窗 |

## 项目结构 (v18 模块化)

```
TradeSnake/
├── backend/
│   ├── data_manager/     # 数据管理模块
│   │   ├── fetcher.py    # 数据获取（腾讯/新浪/东方财富）
│   │   └── cache.py      # 缓存管理（冷热分离）
│   │
│   ├── engine/          # 分析引擎模块
│   │   ├── constants.py  # 常量配置
│   │   ├── cp_engine.py # 战力计算核心
│   │   ├── risk_analyzer.py # 风险评估
│   │   └── history.py   # 战力历史
│   │
│   ├── recommender/     # 智能推荐模块
│   │   ├── recommend_engine.py
│   │   └── swap_calculator.py
│   │
│   ├── simulator/       # 模拟炒股模块
│   │   ├── account.py   # 账户管理
│   │   ├── portfolio.py # 持仓管理
│   │   └── trader.py    # 交易执行
│   │
│   ├── backtester/      # 回测验证模块
│   │   ├── backtest.py  # 回测引擎
│   │   ├── strategies.py # 策略定义
│   │   └── metrics.py   # 绩效指标
│   │
│   ├── api/             # API层
│   ├── models/          # 数据模型
│   └── core/            # 旧模块（保留兼容）
│
├── frontend/             # React前端
├── data/                # 数据存储
└── plan/                # 计划文档
```

### 模块导入示例

```python
# 数据管理
from data_manager import get_stock_data_api, get_single_stock_data

# 分析引擎
from engine import CPEngine, StockCP, RiskAnalyzer

# 智能推荐
from recommender import RecommendEngine, SwapCalculator

# 模拟炒股
from simulator import Account, Portfolio, Trader

# 回测验证
from backtester import BacktestEngine, TopNStrategy
```

## 用户约束系统

系统支持个性化约束配置，推荐结果会自动过滤：

| 约束项 | 说明 | 示例 |
|--------|------|------|
| **capital** | 资金量 | 20000元 |
| **allowed_boards** | 可交易板块 | main(主板)、gem(创业板)、star(科创板)、bge(北交所) |
| **risk_preference** | 风险偏好 | conservative/balanced/aggressive |
| **consider_dividend** | 是否考虑股息 | true/false |

调用 `PUT /api/user/profile` 更新配置后，推荐股票会自动应用新约束。
