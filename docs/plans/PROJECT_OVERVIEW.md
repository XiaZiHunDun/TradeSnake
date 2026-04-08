# TradeSnake 项目概览

## 项目概述

TradeSnake（股市贪吃蛇）将股票市场重新诠释为贪吃蛇游戏，用"战力值"替代金钱衡量股票价值。

**版本**: v19.8

---

## 核心模块

| 模块 | 路径 | 版本 | 状态 |
|------|------|------|------|
| 数据管理 | `data_manager/` | v18.3 + 数据生命周期管理 | ✅ 完整 |
| **股票筛选** | `stock_selector/` | v19.5.2 | ✅ 完整 |
| 分析引擎 | `engine/` | v19.7 | ✅ 完整 |
| 智能推荐 | `recommender/` | v18.4 | ✅ 完整 |
| 模拟炒股 | `simulator/` | v19.7 | ✅ 完整 |
| 回测验证 | `backtester/` | v19.7 | ✅ 完整 |
| 前端 | `frontend/` | v2.2 | 📋 方案已完成，待实现 |
| API层 | `api/` | - | ✅ 完整 |

---

## 项目结构

```
TradeSnake/
├── backend/
│   ├── data_manager/      # 数据管理模块 (v18.3)
│   ├── stock_selector/    # 股票筛选模块 (v19.5.2)
│   ├── engine/             # 分析引擎模块 (v19.7)
│   ├── recommender/        # 智能推荐模块 (v18.4)
│   ├── simulator/          # 模拟炒股模块 (v19.7)
│   ├── backtester/        # 回测验证模块 (v19.7)
│   ├── api/               # API层
│   └── models/            # 数据模型
├── frontend/              # React前端 (待重构)
├── docs/                  # 文档
│   ├── plans/            # 实施方案
│   └── references/       # 参考资料
└── data/                  # 数据存储
```

---

## 战力公式 (v18.2+)

- **权重**: 成长30% + 价值25% + 质量20% + 动量10% + 风险惩罚10%
- **成长分**: 净利润增长(0-300%)×0.6 + 营收增长(-50%-100%)×0.4
- **价值分**: ROE（负值当0，ROE>25%截断）+ PE/PEG/PB评分
- **质量分**: 现金流+毛利率+资产负债率
- **动量分**: 多日动量(60%) + 当日涨跌幅(40%) + 波动率调整
- **风险惩罚**: 根据PE/ROE/增长/波动综合评估

---

## 交易规则

- 最小交易单位: 1手 = 100股
- 买入成本: 佣金0.03% + 过户费0.001%(仅沪市)
- 卖出成本: 佣金0.03% + 印花税0.05% + 过户费0.001%(仅沪市)
- 佣金最低5元/笔
- T+1限制
- 涨停不能买，跌停不能卖
- 初始资金: 20,000元

---

## 数据源

| 数据类型 | 主数据源 | 备用数据源 |
|---------|---------|-----------|
| 股票列表 | akshare | Tushare |
| 实时行情 | 腾讯API | 新浪API |
| 财务数据 | 东方财富 | baostock/akshare |
| 历史K线 | Tushare | - |

---

## 版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v19.8 | 2026-04-08 | 数据生命周期管理实现完成：Phase 1(清理+备份+校验) + Phase 2(VACUUM优化+冷热分离)；回测报告存档（backtest_reports）方案完成 |
| v19.7 | 2026-04-08 | cp_history迁移到data_manager统一管理（SQLite WAL模式）；股票筛选模块子组件完善 |
| v19.6 | 2026-04-08 | 分析引擎新增real_time_score实时因子（权重2%）；股票筛选模块代码实现完成 |
| v19.5.3 | 2026-04-07 | 股票筛选模块新增数据更新频率策略联动（双向数据流优化） |
| v19.5.2 | 2026-04-07 | 股票筛选模块专家评审完善：准入门槛递进 + 挤出机制 + 冲突处理 + TTL清理 + 动态容量 |
| v19.5.1 | 2026-04-07 | 股票筛选模块完善：白名单/黑名单 + 财务预警 + 历史保留 + 指数同步兜底 |
| v19.5 | 2026-04-07 | 股票筛选模块规划：四层股票池 + 动态调整 + 事件驱动 |
| v19.4 | 2026-04-07 | 前端架构v2.0设计：TypeScript + WebSocket + K线图 + 虚拟滚动 |
| v19.3.1 | 2026-04-07 | 清理core目录遗留代码，统一交易费用常量 |
| v19.3 | 2026-04-07 | 回测模块v19.3完成，修复最大回撤计算，新增净值曲线 |
| v19.1 | 2026-04-07 | 模拟炒股模块v19.1完成，市价单/限价单/T+1 |
| v18.4 | 2026-04-07 | 三大场景（换股+纯买入+纯卖出）+ BuyAnalyzer/SellAnalyzer |
| v18.3 | 2026-04-07 | 引擎/推荐模块联动 stock_selector：基于池分层确定分析范围 |
| v18.2 | 2026-04-07 | 模块化重构完成，Kelly仓位管理，技术指标集成 |
| v18.1 | 2026-04-05 | 初始模块化版本 |

---

## 详细文档

| 文档 | 说明 |
|------|------|
| [STOCK_SELECTOR_ARCHITECTURE.md](./STOCK_SELECTOR_ARCHITECTURE.md) | 股票筛选模块方案 v19.5.2 |
| [ENGINE_ARCHITECTURE.md](./ENGINE_ARCHITECTURE.md) | 分析引擎模块方案 v19.7 |
| [RECOMMENDER_ARCHITECTURE.md](./RECOMMENDER_ARCHITECTURE.md) | 智能推荐模块方案 v18.4 |
| [SIMULATOR_ARCHITECTURE.md](./SIMULATOR_ARCHITECTURE.md) | 模拟炒股模块方案 v19.1 |
| [DATA_MANAGER_ARCHITECTURE.md](./DATA_MANAGER_ARCHITECTURE.md) | 数据管理模块方案 v18.3 |
| [BACKTESTER_ARCHITECTURE.md](./BACKTESTER_ARCHITECTURE.md) | 回测验证模块方案 v19.4 |
| [FRONTEND_ARCHITECTURE.md](./FRONTEND_ARCHITECTURE.md) | 前端模块方案 v2.2 |
| [DATA_LIFECYCLE_MANAGEMENT.md](./DATA_LIFECYCLE_MANAGEMENT.md) | 数据生命周期管理方案 v1.4 |

> **注意**：`STOCK_FILTER_STRATEGY.md` 为早期版本，已被 `STOCK_SELECTOR_ARCHITECTURE.md` 替代
