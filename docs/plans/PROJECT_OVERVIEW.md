# TradeSnake 项目概览

## 项目概述

TradeSnake（股市贪吃蛇）将股票市场重新诠释为贪吃蛇游戏，用"战力值"替代金钱衡量股票价值。

**版本**: v21

---

## 产品范围（交易与分析边界）

当前方案与实现下，**股票池分层、战力主算路径、批量行情抽样** 均以 **沪深主板** 为产品边界，与 `StockDataFetcher.get_batch_market_data` 的抽样规则一致：

- **纳入主流程**：沪市主板（不含 688）、深市主板及原中小板等代码段（不含 300）、不含北交所。
- **不纳入本流程**：创业板（300）、科创板（688）、北交所等；不在批量行情与池化主路径中按与主板同等能力扩展。

**说明**：`data_manager` 仍可能拉取「全市场」股票列表或指数成分作列表/标志位；其中「全量」指**数据源维度**，**不等于**对本产品范围外标的承担与主板相同的行情覆盖、入池或战力承诺。业务含义以本节为准。

---

## 核心模块

| 模块 | 路径 | 版本 | 状态 |
|------|------|------|------|
| 数据管理 | `data_manager/` | v18.7（架构文档）+ 数据生命周期管理 | ✅ 完整 |
| **股票筛选** | `stock_selector/` | v19.5.5 | ✅ 完整 |
| 分析引擎 | `engine/` | v19.7 | ✅ 完整 |
| 智能推荐 | `recommender/` | v18.4 | ✅ 完整 |
| 模拟炒股 | `simulator/` | v19.7 | ✅ 完整 |
| 回测验证 | `backtester/` | v19.7 | ✅ 完整 |
| 前端 | `frontend/` | v2.2 | ✅ 已实现基础模块（路由、战力、推荐、回测、模拟页面），工程化待完善 |
| API层 | `api/` | - | ✅ 完整 |

---

## 项目结构

```
TradeSnake/
├── backend/
│   ├── data_manager/      # 数据管理模块 (v18.3)
│   ├── stock_selector/    # 股票筛选模块 (v19.5.5，含 market_snapshot；产品范围仅主板)
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

## 战力公式 (v21)

**权重 (v21数据驱动)**:
- 权重总和：成长50% + 价值0% + 质量5% + 动量28% + 实时2% = **85%**（风险惩罚为独立乘数，不是加性权重）
- **风险惩罚**：×(1 - risk_score/100) × 0.10，最终得分 = 85% × 惩罚系数
- **依据**: 414天 Alpha 分析，growth IC=+0.0104(t=2.46)唯一显著，value IC=-0.009反转

**成长分**: 净利润增长(0-300%)×0.6 + 营收增长(-50%-100%)×0.4
- **价值分**: ROE（负值当0，ROE>25%截断）+ PE/PEG/PB评分
- **质量分**: 现金流+毛利率+资产负债率
- **动量分**: 多日动量(60%) + 当日涨跌幅(40%) + 波动率调整
- **实时分**: 基于分钟K线的均线变化率（v19.6新增，仅核心池计算）
- **风险惩罚**: 根据PE/ROE/增长/波动综合评估

---

## 交易规则 (v21)

- 最小交易单位: 1手 = 100股
- 买入成本: 佣金0.03% + 过户费0.001%(沪深均收，2022年后统一)
- 卖出成本: 佣金0.03% + 印花税0.05% + 过户费0.001%(沪深均收，2022年后统一)
- 佣金最低5元/笔
- T+1限制
- 涨停不能买（涨幅≥9.9%），跌停不能卖（跌幅≤-9.9%）
- **初始资金**: 1,000,000元（simulator默认20000元，API可配置）
- **滑点**: 0.1%

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
| v21 | 2026-05-08 | 战力公式v21：growth IC=+0.0104(t=2.46)唯一显著，权重调整；Walk-Forward v3：Annual 13.89%, Sharpe 0.50, MaxDD 16.30%；trailing stop -8%，rebalance 10天；多轮审查修复Critical/High问题 |
| v19.9.9 | 2026-04-23 | Team模式审查修复：7个模块发现并修复1个P0、2个P1、4个P2问题；文档结构完善（ISSUES+CHECKLIST）；核心池流程审查完成 |
| v19.9.8 | 2026-04-23 | 修复印花税为0.05%；全主板统一10%涨跌停限制；添加API全局异常处理器；修复FullBacktestEngine过户费参数和涨跌停过滤 |
| v19.9.5 | 2026-04-22 | DuckDB跨进程稳定性修复：文件锁(fcntl.flock) + 单连接复用 |
| v19.9 | 2026-04-22 | 核心池优化：minute_kline自动填充收盘后轮换填充核心+活跃池50只/天 |
| v19.8.1 | 2026-04-15 | 补充「产品范围」：交易与分析主路径仅沪深主板，与批量行情抽样一致；澄清全市场列表≠产品边界 |
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
| [stock_selector/STOCK_SELECTOR_ARCHITECTURE.md](./stock_selector/STOCK_SELECTOR_ARCHITECTURE.md) | 股票筛选模块方案 v19.5.5 |
| [engine/ENGINE_ARCHITECTURE.md](./engine/ENGINE_ARCHITECTURE.md) | 分析引擎模块方案 v19.7 |
| [recommender/RECOMMENDER_ARCHITECTURE.md](./recommender/RECOMMENDER_ARCHITECTURE.md) | 智能推荐模块方案 v18.6 |
| [simulator/SIMULATOR_ARCHITECTURE.md](./simulator/SIMULATOR_ARCHITECTURE.md) | 模拟炒股模块方案 v19.1 |
| [data_manager/DATA_MANAGER_ARCHITECTURE.md](./data_manager/DATA_MANAGER_ARCHITECTURE.md) | 数据管理模块方案（见文内版本表） |
| [backtester/BACKTESTER_ARCHITECTURE.md](./backtester/BACKTESTER_ARCHITECTURE.md) | 回测验证模块方案 v19.9 |
| [frontend/FRONTEND_ARCHITECTURE.md](./frontend/FRONTEND_ARCHITECTURE.md) | 前端模块方案 v2.2 |
| [api/API_ARCHITECTURE.md](./api/API_ARCHITECTURE.md) | API模块方案 v19.9.11 |
| [ml/ARCHITECTURE.md](./ml/ARCHITECTURE.md) | 机器学习模块方案 |
| [risk/ARCHITECTURE.md](./risk/ARCHITECTURE.md) | 风险控制模块方案 |
| [DATA_LIFECYCLE_MANAGEMENT.md](./DATA_LIFECYCLE_MANAGEMENT.md) | 数据生命周期管理方案 v1.7 |

> **注意**：`STOCK_FILTER_STRATEGY.md` 为早期版本，已被 `stock_selector/STOCK_SELECTOR_ARCHITECTURE.md` 替代
