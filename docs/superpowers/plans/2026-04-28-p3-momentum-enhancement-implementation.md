# 任务：动量因子增强（P3）

> 日期：2026-04-28  
> 类型：Strategy Enhancement（需谨慎）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：P1 完成 + P2 的分析报告出来后（如果 P2 显示动量 IC 低于预期，需要回报）

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions.

**停止条件**：如果 P2 的分析报告显示动量因子 IC < 0.01（几乎无预测力），停止执行并报告，不要强行优化一个无效因子。

---

## Goal

增强动量因子的丰富度和信号质量：

1. **拆分短期反转 + 中期动量** — A 股短期（1-5 天）有明显的反转效应，中期（20-60 天）有动量效应
2. **成交量确认** — 有量配合的动量更可靠
3. **权重提升** — 动量权重从 8% 提到 15-20%（相应降低 quality）
4. **参数可配置** — 所有新参数写入 constants.py

---

## Context

### A 股动量特征

- **短期反转（1-5 天）**：过去 1 周跌多的股票未来倾向反弹。这是 A 股特有现象（散户情绪驱动）。
- **中期动量（20-60 天）**：过去 1-3 个月涨幅好的股票有持续上涨惯性（机构资金驱动）。
- **长期反转（>120 天）**：超长期涨幅过大的股票倾向回调。
- **成交量确认**：放量上涨 > 缩量上涨；缩量下跌 > 放量下跌（恐慌性下跌可能是底部信号）

### 当前动量计算

`apply_multi_day_momentum` 方法（第 874-903 行）：
- 60% 多日动量（5 天 CP 变化）+ 40% 当日涨跌幅
- 如果多日动量 import 失败（当前 bug），则 100% 当日涨跌幅

### 新设计

```
momentum_score_new = 
    w_reversal × short_term_reversal_score  +  # 短期反转 (1-5天)
    w_momentum × medium_term_momentum_score +  # 中期动量 (20-60天)
    w_volume × volume_confirmation_score     +  # 成交量确认
    w_daily × daily_change_score                # 当日涨跌 (保留兼容)
```

建议初始权重：reversal 25%, momentum 35%, volume 20%, daily 20%

---

## Scope

Allowed changes:

- `backend/engine/cp_engine/cp_engine.py`（增强 `apply_multi_day_momentum` 或新方法）
- `backend/engine/cp_engine/constants.py`（新增动量相关参数）
- `backend/engine/cp_engine/history.py`（如需新的历史数据查询）
- `backend/data_manager/duckdb_store.py`（如需新的 K 线查询方法）
- `backend/tests/test_cp_engine.py`（新增测试）

Out of scope:

- 不修改 API 端点
- 不修改前端

---

## Steps

### Step 1: 新增常量到 constants.py

```python
# 动量因子权重（P3 增强版）
MOMENTUM_WEIGHTS = {
    'short_reversal': 0.25,     # 短期反转 (1-5天)
    'medium_momentum': 0.35,    # 中期动量 (20-60天)  
    'volume_confirm': 0.20,     # 成交量确认
    'daily_change': 0.20,       # 当日涨跌幅
}

# 动量计算参数
MOMENTUM_PARAMS = {
    'reversal_days': 5,         # 短期反转回看天数
    'momentum_days': 20,        # 中期动量回看天数
    'volume_lookback': 10,      # 成交量对比回看天数
    'volume_avg_days': 20,      # 成交量均线天数
}
```

### Step 2: 更新 WEIGHTS

将 momentum 从 0.08 提到 0.18，quality 从 0.20 降到 0.10：

```python
WEIGHTS = {
    'growth': 0.30,
    'value': 0.25,
    'quality': 0.10,        # 从 0.20 降低
    'momentum': 0.18,       # 从 0.08 提高
    'real_time': 0.02,
    'risk_penalty': 0.10,
    # 总权重不含 risk_penalty = 0.85，与之前一致
}
```

注意：如果 P2 分析显示 quality 的 IC 比 momentum 高，则不应降低 quality。**依赖 P2 的数据结论**。

### Step 3: 实现短期反转信号

在 `cp_engine.py` 中新增方法：

```python
def _calc_short_reversal(self, code: str, days: int = 5) -> float:
    """短期反转信号（A 股特有）
    
    逻辑：过去 N 天跌幅越大，反弹概率越高
    返回：0-100 分，跌得越多分越高
    """
    # 从 DuckDB 获取近 N 天收益率
    # reversal_score = -cum_return（取反：跌得多 → 分高）
    # 归一化到 0-100
```

### Step 4: 实现中期动量信号

```python
def _calc_medium_momentum(self, code: str, days: int = 20) -> float:
    """中期动量信号
    
    逻辑：过去 N 天累计涨幅越大，继续上涨概率越高
    返回：0-100 分，涨得越多分越高
    """
    # 从 DuckDB 获取近 N 天收益率
    # 排除最近 5 天（避免与短期反转信号重叠）
    # momentum_score = cum_return[5:days]
    # 归一化到 0-100
```

### Step 5: 实现成交量确认信号

```python
def _calc_volume_confirmation(self, code: str, lookback: int = 10) -> float:
    """成交量确认信号
    
    逻辑：
    - 上涨 + 放量 → 强信号（高分）
    - 上涨 + 缩量 → 弱信号（中分）
    - 下跌 + 缩量 → 底部信号（中高分）
    - 下跌 + 放量 → 恐慌信号（低分）
    返回：0-100 分
    """
    # 计算近 N 天的价格变化方向
    # 计算近 N 天的成交量相对于 20 日均量的比值
    # 组合判断
```

### Step 6: 重构 apply_multi_day_momentum

替换原有的简单组合为多维动量：

```python
def apply_multi_day_momentum(self, momentum_func=None, days=5):
    """多维动量因子 v2.0"""
    from backend.engine.cp_engine.constants import MOMENTUM_WEIGHTS, MOMENTUM_PARAMS
    
    # 批量获取K线数据以避免N+1查询
    codes = [s.code for s in self.stocks]
    bulk_klines = self._get_bulk_klines(codes, lookback=max(
        MOMENTUM_PARAMS['momentum_days'], 
        MOMENTUM_PARAMS['volume_avg_days']
    ) + 5)
    
    for stock in self.stocks:
        klines = bulk_klines.get(stock.code, [])
        
        reversal = self._calc_short_reversal_from_klines(klines, MOMENTUM_PARAMS['reversal_days'])
        momentum = self._calc_medium_momentum_from_klines(klines, MOMENTUM_PARAMS['momentum_days'])
        volume = self._calc_volume_confirmation_from_klines(klines, MOMENTUM_PARAMS['volume_lookback'])
        daily = (max(-10, min(10, stock.change_pct)) + 10) / 20 * 100
        
        combined = (
            reversal * MOMENTUM_WEIGHTS['short_reversal'] +
            momentum * MOMENTUM_WEIGHTS['medium_momentum'] +
            volume * MOMENTUM_WEIGHTS['volume_confirm'] +
            daily * MOMENTUM_WEIGHTS['daily_change']
        )
        
        stock.momentum_score = (combined / 100) * 20 - 10  # 缩放到 -10~10
    
    return self
```

### Step 7: 测试

- [ ] 单元测试每个子信号函数
- [ ] 集成测试整个动量计算流程
- [ ] 验证与原有 API 返回格式兼容（momentum_score 仍在 -10~10 范围）
- [ ] 全量测试不回归

---

## Verification

```bash
python -m pytest backend/tests/test_cp_engine.py -v
python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py
python -c "from backend.engine.cp_engine.cp_engine import CPEngine; print('OK')"
```

---

## Stop Conditions

1. P2 分析显示动量因子 IC < 0.01 → 停止，报告给用户
2. DuckDB 没有足够的 K 线数据（< 60 天）→ 记录哪些数据缺失，继续实现代码但标记需要数据
3. 修改后现有测试大面积失败 → 停止，报告

---

## Completion Report Format

```markdown
## Summary
- 新增的子信号
- 权重变化

## Before/After (if data available)
- 修改前后的动量分分布对比
- 修改前后的 IC 对比（如果 P2 工具可用）

## Verification
- 测试结果

## Data Dependencies
- 需要的最少 K 线历史天数
```
