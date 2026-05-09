# 智能推荐模块方案 - 详细设计

> 本文档是智能推荐模块的详细设计部分，对应 `RECOMMENDER_OVERVIEW.md` 的后续内容。

---

## 五、数据模型

### 5.1 换股建议

```python
{
    'from_code': str,
    'from_name': str,
    'from_cp': float,
    'to_code': str,
    'to_name': str,
    'to_cp': float,
    'cp_improvement': float,
    'net_profit': float,
    'trade_cost': float,
    'breakeven_days': int,
    'action_level': int,       # 0=持有, 1=换股, 2=强烈换股
    'action_label': str,       # 行动标签文字
    'predicted_gain_5d': float, # 预测5日涨幅
    'up_probability_5d': float, # 预测上涨概率
}
```

### 5.2 买入信号

```python
{
    'code': str,
    'name': str,
    'total_cp': float,
    'kelly_position': float,
    'position_amount': float,
    'shares': int,
    'entry_price': float,
    'stop_loss': float,
    'take_profit': float,
    'buy_strength': int,
    'reasons': List[str],
    'warnings': List[str],
    'breakeven_days': int,
    'prompt': str
}
```

### 5.3 卖出信号

```python
{
    'code': str,
    'name': str,
    'quantity': int,
    'cost_price': float,
    'current_price': float,
    'unrealized_pnl': float,
    'unrealized_pnl_pct': float,
    'sell_reason': str,
    'market_mode': str,
    'action': str,
    'action_label': str,
    'action_color': str,
    'urgency': int,
    'next_steps': str,
    'prompt': str
}
```

---

## 六、接口契约

### 6.1 ⚠️ 与 stock_selector 和 engine 的联动

```python
from recommender import RecommendEngine
from engine import CPEngine
from stock_selector import StockSelector, PoolTier

stock_selector = StockSelector()
engine = CPEngine()
recommender = RecommendEngine()

# ─────────────────────────────────────────────
# 推荐候选股票池来源
# ─────────────────────────────────────────────
# 从 stock_selector 获取推荐候选池（核心+活跃）
candidate_codes = (
    stock_selector.get_pool(PoolTier.CORE) +
    stock_selector.get_pool(PoolTier.ACTIVE)
)

# 从 engine 获取战力数据
engine.calculate_for_codes(candidate_codes)

# ─────────────────────────────────────────────
# 换股建议
# ─────────────────────────────────────────────
swaps = recommender.get_swap_suggestions(
    holdings=[{'code': '000001', 'stock': engine.get_by_code('000001'), 'quantity': 1000, 'cost_price': 10.0}],
    all_stocks=engine.get_stocks_by_codes(candidate_codes),
    principal=100000,
    holding_days=30
)

# ─────────────────────────────────────────────
# 买入信号
# ─────────────────────────────────────────────
buys = recommender.get_buy_signals(
    stocks=engine.get_top(50),
    principal=100000,
    risk_preference='balanced'
)

# 卖出信号
sells = recommender.get_sell_signals(
    holdings=[{'code': '000001', 'stock': engine.get_by_code('000001'), 'quantity': 1000, 'cost_price': 10.0}],
    market_mode='normal'
)
```

### 6.2 接收 stock_selector 回调 v18.5

```python
class RecommenderCallback:
    """接收 stock_selector 的池状态变化通知 v18.5"""

    def __init__(self, engine: RecommendEngine):
        self._engine = engine
        self.candidate_pool: List[str] = []      # 推荐候选池
        self.priority_candidates: Set[str] = set()  # 优先候选集
        self.watchlist: Dict[str, List[str]] = {}   # 监控列表 {code: [warnings]}

    def on_pool_changed(self, tier: PoolTier, added: List[str], removed: List[str]):
        """池变化时更新推荐候选池"""
        if tier not in [PoolTier.CORE, PoolTier.ACTIVE]:
            return
        for code in added:
            if code not in self.candidate_pool:
                self.candidate_pool.append(code)
        self.candidate_pool = [c for c in self.candidate_pool if c not in removed]
        for code in removed:
            self.priority_candidates.discard(code)

    def on_stock_upgraded_to_core(self, code: str):
        """股票晋级到核心池 → 优先推荐"""
        self.priority_candidates.add(code)
        if code not in self.candidate_pool:
            self.candidate_pool.append(code)

    def on_financial_warning(self, code: str, warnings: List[str]):
        """财务预警时 → 从推荐移除，加入监控"""
        self.candidate_pool = [c for c in self.candidate_pool if c != code]
        self.priority_candidates.discard(code)
        self.watchlist[code] = warnings

    def get_candidate_pool(self) -> List[str]:
        """获取当前候选池"""
        return self.candidate_pool.copy()

    def get_priority_candidates(self) -> Set[str]:
        """获取优先候选集"""
        return self.priority_candidates.copy()

    def get_watchlist(self) -> Dict[str, List[str]]:
        """获取监控列表"""
        return self.watchlist.copy()
```

---

## 七、版本规划

### 7.1 当前状态 (v18.5)

- [x] 换股计算器
- [x] 股票过滤器
- [x] 预测融合 RecommenderCallback v19.8 ✅

### 7.2 待实现

**P0 必须**：
- [x] 买入分析器 BuyAnalyzer ✅
- [x] 卖出分析器 SellAnalyzer ✅
- [x] prompts.py 推荐理由生成 ✅
- [x] Kelly仓位集成 ✅

**P1 建议**：
- [x] 流动性过滤 ✅
- [ ] 财报季风险过滤
- [ ] 大盘模式联动

### 7.3 阶段规划

```
v18.2: 基础换股计算器 ✅

v18.5 (当前):
├── P0: BuyAnalyzer 买入分析
├── P0: SellAnalyzer 卖出分析
├── P0: prompts.py 理由生成
└── P0: Kelly仓位计算

v18.x: 完善风控、流动性、财报季
```

---

## 八、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v18.6 | 2026-04-14 | 补充融合公式：归一化处理(cp/100, gain/50)、置信度乘数×confidence |
| v18.5 | 2026-04-09 | ✅ 预测融合(v19.8)：PredictionFusion实现战力与涨幅/概率预测融合；删除PositionCalculator死代码；BuySignal新增预测字段 |
| v18.4 | 2026-04-07 | ✅ P0全部完成：三大场景设计（换股+纯买入+纯卖出），BuyAnalyzer/SellAnalyzer/Kelly仓位/StockFilter五大过滤器/prompts.py |
| v18.3 | 2026-04-07 | 强化设计：涨跌停过滤、滑点成本、prompts.py |
| v18.2 | 2026-04-07 | 初始版本，基础推荐引擎 + 换股计算 + 过滤器 |

---

## 九、相关文档

- [项目概览](../PROJECT_OVERVIEW.md) - 项目整体介绍
- [分析引擎方案](../engine/ENGINE_ARCHITECTURE.md) - 战力计算模块
- [数据管理方案](../data_manager/DATA_MANAGER_ARCHITECTURE.md) - 数据获取模块
- [专家评审](../../reviews/专家评审/) - 评审文档参考
