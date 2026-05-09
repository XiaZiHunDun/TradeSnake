# TradeSnake - 股市贪吃蛇

将股票市场重新诠释为一场贪吃蛇游戏，用"战力值"替代金钱衡量股票价值。

## 项目概述

TradeSnake（股市贪吃蛇）将股市比作贪吃蛇游戏，核心理念是重新构建股票价值体系，不以金钱衡量，而是用"战力值"等新单位衡量股票价值。通过置换、低价值换高价值来提升自身价值。

**说明（产品范围）**：当前仓库内股票池、战力主算与批量行情抽样以 **沪深主板** 为边界；细节见 `docs/plans/PROJECT_OVERVIEW.md`「产品范围」。

## 技术栈

- **后端**: Python FastAPI
- **前端**: React + Vite + TailwindCSS
- **数据源**: 东方财富数据中心API

## 战力公式 (v19.9 综合版)

```
总战力 = (成长分×40% + 价值分×40% + 动量分×20%) × 风险调整因子
```

> ⚠️ 战力公式已升级到 v19，详见 `docs/plans/PROJECT_OVERVIEW.md`

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
- [x] 智能推荐（价值型/成长型/趋势型/质量型）
- [x] 历史战力记录
- [x] 榜单变化追踪
- [x] 风险评估
- [x] 调仓建议

## 运行

### 后端
```bash
conda activate tradesnake
python -m uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8001
```
> 注意：从项目根目录运行，不要 `cd backend`。启动约需60秒（数据初始化）。

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
- `GET /api/cp/stock/{code}` - 获取单只股票详情
- `POST /api/refresh?limit=200` - 手动刷新数据（限流: 5次/分钟）

### 推荐API
- `GET /api/cp/recommend?category=value|growth|momentum|quality` - 获取推荐股票（已应用用户约束过滤）

### 用户配置API
- `GET /api/user/profile` - 获取用户配置（资金、板块、风险偏好、股息考虑）
- `PUT /api/user/profile` - 更新用户配置

### 统计API
- `GET /api/stats/market` - 市场统计

### 历史API
- `GET /api/history/changes?days=7` - 战力变化
- `GET /api/history/{code}?days=30` - 单只股票历史
- `GET /api/history/rankings?days=30&limit=10` - 历史排行

## 项目结构

```
TradeSnake/
├── backend/
│   ├── api/             # API层
│   ├── config.py        # 集中式路径配置
│   ├── data_manager/    # 数据获取、缓存、存储
│   ├── engine/          # 战力、涨幅、概率预测
│   ├── recommender/     # 推荐、融合
│   ├── simulator/       # 模拟账户、持仓、交易
│   ├── backtester/      # 回测验证
│   └── models/          # Pydantic模型
├── frontend/            # React前端
├── tests/               # 后端测试
├── data/                # 数据存储
└── docs/plans/          # 计划文档
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
