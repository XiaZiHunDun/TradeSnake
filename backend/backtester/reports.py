"""
回测报告生成 - Reports v19.3
"""

from typing import Dict
from .metrics import BacktestResult


BACKTEST_DISCLAIMER = """
⚠️ 回测结果仅供参考，不构成投资建议。
- 过去表现不代表未来收益
- 回测存在简化假设，可能与实盘差异较大
- 幸存者偏差：已退市股票未纳入回测
"""


def generate_report(result: BacktestResult) -> str:
    """生成Markdown格式回测报告

    Args:
        result: 回测结果

    Returns:
        Markdown格式报告字符串
    """
    # 判断策略有效性
    effective = "✅ 有效" if result.excess_return > 0 else "⚠️ 无明显优势" if result.excess_return == 0 else "❌ 无效"

    # 绩效指标参考
    sharpe_评估 = "优秀" if result.sharpe_ratio >= 1.5 else "良好" if result.sharpe_ratio >= 1.0 else "一般" if result.sharpe_ratio >= 0.5 else "较差"
    calmar_评估 = "优秀" if result.calmar_ratio >= 2.0 else "良好" if result.calmar_ratio >= 1.0 else "一般" if result.calmar_ratio >= 0.5 else "较差"
    maxdd_评估 = "优秀" if result.max_drawdown <= 10 else "良好" if result.max_drawdown <= 20 else "一般" if result.max_drawdown <= 30 else "较差"

    report = f"""# 回测报告

## 基本信息

| 项目 | 值 |
|------|-----|
| 策略名称 | {result.strategy_name} |
| 回测期 | {result.start_date} ~ {result.end_date} |
| 初始资金 | {result.initial_capital:.2f} |
| 最终资金 | {result.final_capital:.2f} |

## 绩效指标

### 收益指标

| 指标 | 策略 | 评估 |
|------|------|------|
| 总收益率 | {result.total_return:.2f}% | - |
| 年化收益率 | {result.annual_return:.2f}% | - |
| 基准收益率 | {result.benchmark_return:.2f}% | - |
| 超额收益 | {result.excess_return:.2f}% | {effective} |

### 风险指标

| 指标 | 值 | 评估 |
|------|-----|------|
| 最大回撤 | {result.max_drawdown:.2f}% | {maxdd_评估} |
| 年化波动率 | {result.volatility:.2f}% | - |
| 夏普比率 | {result.sharpe_ratio:.2f} | {sharpe_评估} |
| 卡玛比率 | {result.calmar_ratio:.2f} | {calmar_评估} |
| 最大连盈 | {result.max_consecutive_win}天 | - |
| 最大连亏 | {result.max_consecutive_loss}天 | - |

### 交易指标

| 指标 | 值 |
|------|-----|
| 总交易次数 | {result.total_trades} |
| 盈利次数 | {result.winning_trades} |
| 亏损次数 | {result.losing_trades} |
| 交易胜率 | {result.win_rate:.2f}% |
| 盈亏比 | {result.profit_loss_ratio:.2f} |
| 平均持仓天数 | {result.avg_holding_days:.1f}天 |

## 回测结论

"""

    # 生成结论
    conclusions = []

    if result.excess_return > 10:
        conclusions.append(f"✅ 策略超额收益显著（{result.excess_return:.1f}%），跑赢基准明显")
    elif result.excess_return > 0:
        conclusions.append(f"✅ 策略跑赢基准（{result.excess_return:.1f}%），具有一定的超额收益能力")
    elif result.excess_return < 0:
        conclusions.append(f"❌ 策略跑输基准（{result.excess_return:.1f}%），需要优化策略")

    if result.sharpe_ratio >= 1.5:
        conclusions.append(f"✅ 夏普比率{result.sharpe_ratio:.2f}，风险调整收益优秀")
    elif result.sharpe_ratio >= 1.0:
        conclusions.append(f"✅ 夏普比率{result.sharpe_ratio:.2f}，风险调整收益良好")

    if result.max_drawdown <= 10:
        conclusions.append(f"✅ 最大回撤{result.max_drawdown:.1f}%，风险控制优秀")
    elif result.max_drawdown <= 20:
        conclusions.append(f"⚠️ 最大回撤{result.max_drawdown:.1f}%，风险控制良好")
    elif result.max_drawdown >= 30:
        conclusions.append(f"❌ 最大回撤{result.max_drawdown:.1f}%，风险较大")

    if result.win_rate >= 60:
        conclusions.append(f"✅ 交易胜率{result.win_rate:.1f}%，盈利概率较高")
    elif result.win_rate < 40:
        conclusions.append(f"⚠️ 交易胜率{result.win_rate:.1f}%，盈利概率偏低")

    if not conclusions:
        conclusions.append("策略表现一般，建议优化参数或策略逻辑")

    for c in conclusions:
        report += f"- {c}\n"

    report += f"""
---

## 交易明细（最近10笔）

| 日期 | 代码 | 名称 | 操作 | 价格 | 数量 | 盈亏 | 原因 |
|------|------|------|------|------|------|------|------|
"""

    # 添加最近10笔交易
    for trade in result.trades[-10:]:
        report += f"| {trade.trade_date} | {trade.code} | {trade.name} | {trade.action} | {trade.price:.2f} | {trade.quantity} | {trade.profit:.2f} | {trade.reason} |\n"

    report += f"""
---

## 净值曲线

```
日期          净值
"""

    import datetime
    # 优先使用net_value_curve（已包含净值），否则从equity_curve计算
    if result.net_value_curve:
        curve = result.net_value_curve
        for date, net_val in list(curve.items())[-20:]:
            bar = "█" * int((net_val - 1) * 50 + 25)
            report += f"{date}  {net_val:>10.4f}  {bar}\n"
    else:
        # 兼容旧数据：从equity_curve计算净值
        for date, total_val in list(result.equity_curve.items())[-20:]:
            net_val = total_val / result.initial_capital
            bar = "█" * int((net_val - 1) * 50 + 25)
            report += f"{date}  {net_val:>10.4f}  {bar}\n"

    report += f"""
```

---

## 免责声明

{BACKTEST_DISCLAIMER}

*报告生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

    return report


def save_report(result: BacktestResult, path: str):
    """保存报告到文件

    Args:
        result: 回测结果
        path: 文件路径
    """
    report = generate_report(result)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(report)
