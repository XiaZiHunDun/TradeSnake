# TradeSnake - 股市贪吃蛇

将股票市场重新诠释为一场贪吃蛇游戏，用"战力值"替代金钱衡量股票价值。

## 项目概述

TradeSnake（股市贪吃蛇）将股市比作贪吃蛇游戏，核心理念是重新构建股票价值体系，不以金钱衡量，而是用"战力值"等新单位衡量股票价值。通过置换、低价值换高价值来提升自身价值。

## 技术栈

- **后端**: Python FastAPI + SQLite
- **前端**: React + Vite + TailwindCSS + ECharts
- **数据源**: 东方财富数据中心API

## 战力公式 (v14 赚钱版)

```
总战力 = (成长分×30% + 价值分×25% + 质量分×20% + 动量分×15%) × 风险调整因子
```

### 因子计算

**成长分(30%)**: 净利润增长(0-300%)×0.6 + 营收增长(-50%-100%)×0.4

**价值分(25%)**: ROE基础分 + PE健康度 + PEG估值 + PB市净率
- PE评分: 5-20区间最优(10分)，>50扣分
- PEG评分: PEG<0.5最优(+8分)，PEG>2扣分(-5分)
- PB评分: PB<1最优(破净股+8分)

**质量分(20%)**: 现金流质量 + 毛利率 + 资产负债率
- 现金流/ROE比例合理(0.5-3倍): +15分
- 毛利率>30%(护城河): +10分
- 资产负债率<50%: +3分

**动量分(15%)**: 当日涨跌幅（限制在-10到10之间）

### 风险评估（风险调整因子）

风险分数（0-100，越高风险越大）:

- **PE风险**: 亏损(30分) / PE>100(20分) / PE>50(10分) / PE<5(5分)
- **ROE风险**: ROE<0(25分) / ROE<5(10分)
- **增长风险**: 净利润下降<-50%(15分) / 净利润下降<0(5分)
- **波动风险**: 涨跌幅>8%(15分) / 涨跌幅>5%(8分)

**最终战力 = 基础战力 × (1 - 风险比例×10%)**

### 赚钱逻辑

- **价值型**: PEG<1 + 高ROE + 正现金流 + 低PB
- **成长型**: PEG<1 + 营收利润双增长 + 合理PE
- **质量型**: 高毛利率 + 低负债 + 正现金流

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
- `GET /api/cp/recommend?category=value|growth|momentum|quality|allround` - 获取推荐股票

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

## 项目结构

```
TradeSnake/
├── backend/
│   ├── api/              # API路由
│   ├── core/             # 战力计算引擎
│   ├── data/             # 数据获取
│   ├── models/           # 数据模型
│   └── tests/            # 单元测试
├── frontend/
│   ├── src/
│   │   ├── components/   # 公共组件
│   │   ├── hooks/        # 自定义Hooks
│   │   ├── pages/        # 页面组件
│   │   └── utils/        # 工具函数
│   └── public/
└── README.md
```
