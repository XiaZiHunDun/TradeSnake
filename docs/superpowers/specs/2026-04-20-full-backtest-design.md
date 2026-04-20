# 完整回测实现方案 v1.0

> 日期：2026-04-20
> 目标：实现基于历史战力数据的完整回测

## 一、目标

实现基于历史战力数据的完整回测功能，支持3个月回测期，核心池约300只股票。

## 二、数据现状

| 数据 | 当前状态 | 需要补充 |
|------|----------|----------|
| DuckDB 日K线 | ✅ 完整（2024-04至今） | 无 |
| SQLite `stocks` 表财务数据 | ✅ 有 | 无 |
| SQLite `financial_history` 表 | ⚠️ 需检查 | 如无数据需填充 |
| cp_history | ❌ 只有约1个月 | 需回填3个月历史战力 |

## 三、实施步骤

### Step 1: 检查财务历史数据

```python
# 检查 financial_history 表数据量
result = db.query("SELECT COUNT(DISTINCT code), COUNT(*) FROM financial_history")
# 预期：每只股票约16-20条季度数据
```

### Step 2: 回填历史战力

**扩展 `CPHistoryBatchCalculator`** 支持历史战力计算：

```python
def calculate_historical_cp(
    self,
    dates: List[str],           # 要计算的日期列表
    codes: List[str] = None,    # 股票代码列表，默认核心池
    days_back: int = 65         # 3个月约65个交易日
) -> FillResult
```

**核心逻辑**：
1. 对每个交易日 D：
   - 获取 D 日的核心池股票列表（约300只）
   - 对每只股票，找到 D 之前最新发布的季度财务数据
   - 结合历史K线数据，使用 CPEngine 计算战力
   - 保存到 cp_history 表

**历史财务匹配规则**：
| 回测日期 | 使用财务数据 | 说明 |
|----------|-------------|------|
| 2026-01-15 | 2025-Q3 | Q3报10月发布 |
| 2026-04-15 | 2025-Q4 | 年报4月发布 |

### Step 3: 实现完整回测API

**新增API**：
```python
@router.get("/api/backtest/full")
async def full_backtest(
    start_date: str = Query(..., regex="^\\d{4}-\\d{2}-\\d{2}$"),
    end_date: str = Query(..., regex="^\\d{4}-\\d{2}-\\d{2}$"),
    strategy: str = Query("top", pattern="^(top|value|growth|momentum|quality)$"),
    top_n: int = Query(10, ge=1, le=50),
    initial_capital: float = Query(20000, gt=0)
) -> FullBacktestResponse
```

**返回数据**：
```python
class FullBacktestResponse(BaseModel):
    start_date: str
    end_date: str
    strategy: str
    initial_capital: float
    final_value: float
    total_return: float           # 总收益率
    annualized_return: float     # 年化收益率
    sharpe_ratio: float          # 夏普比率
    max_drawdown: float          # 最大回撤
    win_rate: float              # 胜率
    total_trades: int            # 总交易次数
    equity_curve: List[Dict]     # 每日净值曲线
    trades: List[Dict]           # 交易记录
```

### Step 4: 回测执行流程

```
T日收盘:
  1. 获取T日战力数据（从 cp_history）
  2. 策略 select_stocks() → 目标持仓列表
  3. 生成调仓信号（仅当列表变化时）

T+1日收盘:
  4. 按T+1日收盘价执行成交
  5. 涨跌停股票跳过
  6. T+1限制检查
  7. 更新持仓、记录净值
```

**回测规则**：
- T+1限制：今日买的股票不能卖
- 最大持仓天数：默认5个交易日
- 费用：佣金(0.03%) + 印花税(0.1%卖出) + 过户费(0.002%)
- 涨跌停限制：涨停不能买，跌停不能卖

## 四、预估耗时

| 步骤 | 工作量 | 说明 |
|------|--------|------|
| 财务历史检查 | <1分钟 | SQL查询 |
| 财务历史填充 | 0-3小时 | 如需填充，5000只×16季度 |
| 历史战力回填 | 约20分钟 | 300只×65天 |
| 完整回测执行 | 5-10秒 | 65个交易日 |

## 五、文件修改

| 文件 | 修改内容 |
|------|----------|
| `backend/data_manager/filler.py` | 扩展 `CPHistoryBatchCalculator.calculate_historical_cp()` |
| `backend/backtester/backtest.py` | 新增 `FullBacktestEngine` 类 |
| `backend/api/router.py` | 新增 `/api/backtest/full` 端点 |
| `backend/models/schemas.py` | 新增 `FullBacktestResponse` |

## 六、兼容性

- 保留现有的简化回测API `/api/backtest/simple`
- 新API命名为 `/api/backtest/full` 区分

## 七、风险

1. **财务历史数据缺失**：如 `financial_history` 表无数据，需先运行填充
2. **计算量大**：300只×65天计算需要约20分钟，应后台执行
3. **内存占用**：回测过程中需加载历史战力数据，控制在合理范围
