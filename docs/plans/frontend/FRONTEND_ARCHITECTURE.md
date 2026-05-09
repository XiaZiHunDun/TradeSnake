# 前端模块方案

> 本文档是前端模块的入口索引，实际内容拆分到以下两个文件中：

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| [FRONTEND_OVERVIEW.md](./FRONTEND_OVERVIEW.md) | 概述、输入输出、一、设计目标、二、模块结构、三、API层与实时数据 | ~358 |
| [FRONTEND_DETAIL.md](./FRONTEND_DETAIL.md) | 四、页面与布局设计、五、组件层级设计、六、状态管理方案、七、主题与UI设计、八、API端点对应、九~十二 | ~527 |

## 内容速览

### FRONTEND_OVERVIEW.md
- **概述**：前端职责（数据展示、用户交互、操作执行）、v19.8预测分析模块集成
- **输入输出**：输入（backend/api、WebSocket、用户交互）、输出（UI界面、API请求、用户操作指令）
- **设计目标**：问题诊断（7项）、设计原则（5项）、专家设计参考（5份）、技术选型（React18+TS/Vite/ECharts/Zustand/AntD5+Tailwind）
- **模块结构**：目录设计（modules/shared）、与后端模块对应（market→engine/stock→engine/portfolio→simulator等）
- **API层与实时数据**：TanStack Query REST客户端、WebSocket服务（重连机制）、Zustand行情状态管理、@tanstack/react-virtual虚拟滚动

### FRONTEND_DETAIL.md
- **页面与布局设计**：8个页面清单、侧边栏+主内容双栏布局、响应式策略（桌面/平板/移动）、个股详情页（无K线）
- **组件层级设计**：Atoms/Molecules/Organisms三级体系、StockCard/PriceDisplay/SortableTable代码示例
- **状态管理**：4个Zustand Store（quotes/watchlist/portfolio/ui）、缓存策略（5秒~永久）、性能优化（虚拟滚动/Web Worker/懒加载）
- **主题与UI设计**：专业金融配色（深色#0a0e17/红涨绿跌）、可访问性（ARIA/键盘导航）、字体规范（Inter/JetBrains Mono）、间距系统（xs~2xl）
- **API端点对应**：核心API（11项）、预测分析API（4项）、验证报告API（5项）、回测风险API（5项）、历史系统API（6项）
- **开发规范**：命名规范、代码组织、质量工具、开发阶段建议（5个Phase）

## 原文档拆分说明

原 `FRONTEND_ARCHITECTURE.md`（863行）拆分为两个文件以降低单文件大小，改进文档加载性能和可维护性。
