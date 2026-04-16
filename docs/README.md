# TradeSnake 文档中心

**产品范围**：当前方案下，股票池、战力主算与批量行情抽样以 **沪深主板** 为边界（详见 `plans/PROJECT_OVERVIEW.md`「产品范围」及 `stock_selector/STOCK_SELECTOR_ARCHITECTURE.md`）。

---

## 目录结构

```
docs/
├── README.md
├── plans/                          # 实施方案
│   ├── PROJECT_OVERVIEW.md       # 项目概览
│   ├── data_manager/DATA_MANAGER_*.md   # 数据管理模块方案
│   └── stock_selector/STOCK_SELECTOR_*.md  # 股票筛选模块方案
├── references/                     # 参考资料
│   ├── 01_旧版设计文档.md
│   ├── 02_数据来源方案.md
│   └── 专家设计/                  # 专家设计稿
│       ├── 1.md
│       ├── 2.md
│       ├── 3.md
│       ├── 4.md
│       └── 5.md
└── reviews/                       # 评审意见
    ├── 专家评审/
    └── 爱尔希评审/
```

---

## 实施方案 (plans/)

| 文件 | 说明 | 状态 |
|------|------|------|
| `PROJECT_OVERVIEW.md` | 项目概览 | ✅ |
| `data_manager/DATA_MANAGER_ARCHITECTURE.md` | 数据管理模块方案（当前 v18.7 与实现同步说明见文内版本表） | ✅ 完整 |
| `stock_selector/STOCK_SELECTOR_ARCHITECTURE.md` | 股票筛选模块方案 v19.5.5（含产品范围：仅主板） | ✅ 完整 |
| `engine/ENGINE_ARCHITECTURE.md` | 分析引擎模块方案 v18.1.6 | ✅ 完整 |

---

## 参考资料 (references/)

### 旧版文档

| 文件 | 说明 |
|------|------|
| `01_旧版设计文档.md` | 早期设计文档 |
| `02_数据来源方案.md` | 数据来源方案 v4 |

### 专家设计稿 (专家设计/)

| 文件 | 说明 |
|------|------|
| `1.md` | 问题分析 |
| `2.md` | 解决方案 |
| `3.md` | 缓存设计 |
| `4.md` | 详细设计 |
| `5.md` | 实施计划 |

---

## 评审意见 (reviews/)

### 专家评审 (reviews/专家评审/)

| 文件 | 说明 |
|------|------|
| `1.md` | 针对问题分析 |
| `2.md` | 针对解决方案 |
| `3.md` | 针对缓存设计 |
| `4.md` | 针对详细设计 |
| `5.md` | 针对实施计划 |

### 爱尔希评审 (reviews/爱尔希评审/)

| 文件 | 说明 |
|------|------|
| `REVIEW_20260401*.md` | 评审报告（多版本） |
| `RESPONSE_v5_momentum.md` | 工程师回复 |
| `ERXI_RESPONSE_trading_cost.md` | 补充建议 |

---

## 项目主文档

| 文件 | 位置 | 说明 |
|------|------|------|
| `README.md` | 根目录 | 项目主文档 |

---

## 更新记录

| 日期 | 操作 |
|------|------|
| 2026-04-06 | 文档整理，建立清晰目录结构 |
