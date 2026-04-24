"""
数据模型 - TradeSnake Models
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Tuple, Any


class StockCPData(BaseModel):
    """股票战力数据"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    price: float = Field(..., description="当前价格（元）")
    pe: float = Field(..., description="市盈率（TTM）")
    roe: float = Field(..., description="净资产收益率（%），越高越好")
    net_profit_growth: float = Field(..., description="净利润增长率（%），正值为增长")
    revenue_growth: float = Field(..., description="营收增长率（%），正值为增长")
    change_pct: float = Field(..., description="今日涨跌幅（%）")
    growth_score: float = Field(..., description="成长性得分（0-100）")
    value_score: float = Field(..., description="价值得分（0-100）")
    momentum_score: float = Field(..., description="动量得分（0-100）")
    quality_score: float = Field(default=0, description="质量得分（0-100），0表示无数据")
    total_cp: float = Field(..., description="综合战力评分（0-100）")
    risk_score: float = Field(default=0, description="风险评分（0-100），越高风险越大")
    risk_level: str = Field(default='low', description="风险等级：low/medium/high")
    # 扩展字段
    peg: float = Field(default=0, description="PEG估值，<1为低估")
    pb: float = Field(default=0, description="市净率，越低越有估值优势")
    gross_margin: float = Field(default=0, description="毛利率（%），越高盈利能力越强")
    revenue: float = Field(default=0, description="主营收入（亿元）")
    cashflow: float = Field(default=0, description="经营现金流（亿元）")
    debt_ratio: float = Field(default=0, description="资产负债率（%），越低越安全")
    dividend_yield: float = Field(default=0, description="股息率（%），越高投资者回报越好")
    market_cap: float = Field(default=0, description="总市值（亿元）")
    high: float = Field(default=0, description="历史最高价（元）")
    low: float = Field(default=0, description="历史最低价（元）")
    data_quality: str = Field(default='low', description="数据质量：high/medium/low")
    # 板块信息
    board_type: str = Field(default='main', description="板块类型：main主板/gem创业板/star科创板/bge北交所")
    board_name: str = Field(default='主板', description="板块显示名称")
    can_trade_newbie: bool = Field(default=True, description="新手是否可以交易")
    trade_requirement: str = Field(default='新手可交易', description="交易权限要求说明")
    # 新增字段
    sector: str = Field(default='', description="所属行业板块")
    momentum_3d: float = Field(default=0, description="3日动量涨幅（%），正值表示上涨动量")
    momentum_5d: float = Field(default=0, description="5日动量涨幅（%），正值表示上涨动量")
    net_benefit_hint: str = Field(default='', description="净收益提示文字")
    # 安全性指标
    current_ratio: float = Field(default=0, description="流动比率，>1表示短期偿债能力良好")
    interest_coverage: float = Field(default=0, description="利息保障倍数，越高越好")
    deducted_net_profit: float = Field(default=0, description="扣非净利润（亿元），反映主业真实盈利")
    # v19.9.5 融合推荐字段
    kelly_position: float = Field(default=0, description="Kelly公式建议仓位比例（%），0表示无建议")
    predicted_gain_5d: float = Field(default=0, description="预测5日涨幅（%），正值表示预计上涨")
    up_probability_5d: float = Field(default=0, description="5日上涨概率（0-1），>0.5表示看涨")
    prediction_confidence: float = Field(default=0, description="预测置信度（0-1），越高越可靠")
    fused_score: float = Field(default=0, description="融合得分，综合战力+预测的加权得分")


class CPListResponse(BaseModel):
    """战力榜单响应"""
    total: int = Field(..., description="股票总数")
    data: List["SingleStockResponse"] = Field(..., description="股票战力数据列表")
    updated_at: Optional[str] = Field(None, description="数据更新时间，ISO格式")
    error: Optional[str] = Field(None, description="错误信息，无错误时为None")


class PoolStatsResponse(BaseModel):
    """股票池统计响应"""
    core_count: int = Field(..., description="核心池股票数量")
    active_count: int = Field(..., description="活跃池股票数量")
    observe_count: int = Field(..., description="观察池股票数量")
    total_count: int = Field(..., description="所有池股票总数")


class SwapSuggestion(BaseModel):
    """换股建议"""
    from_code: str = Field(..., description="原股票代码")
    from_name: str = Field(..., description="原股票名称")
    from_cp: float = Field(..., description="原股票战力评分")
    to_code: str = Field(..., description="目标股票代码")
    to_name: str = Field(..., description="目标股票名称")
    to_cp: float = Field(..., description="目标股票战力评分")
    cp_improvement: float = Field(..., description="战力提升值")
    trade_cost: float = Field(..., description="交易成本（元）")
    net_benefit: float = Field(..., description="净收益（元），考虑交易成本后的收益")
    holding_days_equivalent: int = Field(..., description="等效持有天数，需要持有这么久才能弥补交易成本")
    action_level: str = Field(..., description="操作建议等级：strong_buy强烈买入/buy买入/hold持有/danger危险")
    action_label: str = Field(..., description="操作建议标签文字")


class RecommendResponse(BaseModel):
    """增强版推荐响应"""
    category: str = Field(..., description="推荐类别")
    total: int = Field(..., description="推荐股票总数")
    data: List[StockCPData] = Field(..., description="推荐股票列表")
    swap_suggestions: List[SwapSuggestion] = Field(default_factory=list, description="换股建议列表")
    portfolio_diversity: Dict[str, int] = Field(default_factory=dict, description="组合多样性统计，按行业板块分组")
    filters_applied: Dict[str, Any] = Field(default_factory=dict, description="应用的筛选条件")
    risk_preference: str = Field(default='aggressive', description="风险偏好：conservative保守/balanced平衡/aggressive激进")
    error: Optional[str] = Field(None, description="错误信息，无错误时为None")


class SingleStockResponse(StockCPData):
    """单只股票响应，继承自股票战力数据"""
    pass


class Holding(BaseModel):
    """持仓"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    quantity: int = Field(..., description="持股数量（股），必须是100的整数倍")
    cost_price: float = Field(..., description="成本价（元）")


class PersonalCPResponse(BaseModel):
    """个人战力响应"""
    total_cp: float = Field(..., description="个人投资组合总战力评分")
    holdings: List[Dict[str, Any]] = Field(..., description="持仓列表，每项包含code/name/quantity/cost_price")
    updated_at: str = Field(..., description="数据更新时间，ISO格式")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态：healthy正常/unhealthy异常")
    timestamp: str = Field(..., description="检查时间戳")
    data_fresh: bool = Field(..., description="数据是否最新")
    last_update: Optional[str] = Field(None, description="最后数据更新时间，ISO格式")
    stocks_count: int = Field(default=0, description="当前股票数量")


class MarketStatsResponse(BaseModel):
    """市场统计响应"""
    total_stocks: int = Field(..., description="市场股票总数")
    avg_cp: float = Field(..., description="市场平均战力评分")
    high_cp_count: int = Field(..., description="高战力股票数量（战力>70）")
    mid_cp_count: int = Field(..., description="中战力股票数量（战力50-70）")
    low_cp_count: int = Field(..., description="低战力股票数量（战力<50）")
    avg_change: float = Field(..., description="市场平均涨跌幅（%）")
    rising_stocks: int = Field(..., description="上涨股票数量")
    falling_stocks: int = Field(..., description="下跌股票数量")
    unchanged_stocks: int = Field(..., description="平盘股票数量")


class TradeCostDetail(BaseModel):
    """交易成本明细"""
    principal: float = Field(..., description="本金（元）")
    sell_commission: float = Field(..., description="卖出佣金（元），通常为成交额的0.03%-0.05%")
    sell_stamp_tax: float = Field(..., description="卖出印花税（元），成交额的0.1%")
    sell_transfer_fee: float = Field(..., description="卖出过户费（元），成交额的0.002%")
    buy_commission: float = Field(..., description="买入佣金（元），通常为成交额的0.03%")
    buy_transfer_fee: float = Field(..., description="买入过户费（元），成交额的0.002%")
    total_cost: float = Field(..., description="总交易成本（元）")
    cost_rate: float = Field(..., description="成本费率（%），成本占本金的比例")


class TradeDecisionResponse(BaseModel):
    """换股决策响应 v15"""
    from_cp: float = Field(..., description="原股票战力评分")
    to_cp: float = Field(..., description="目标股票战力评分")
    cp_diff: float = Field(..., description="战力差值（目标-原）")
    expected_return: float = Field(..., description="预期收益率（%）")
    holding_days: int = Field(..., description="预计持有天数")
    gross_profit: float = Field(..., description="毛收益（元）")
    trade_cost: float = Field(..., description="交易成本（元）")
    net_profit: float = Field(..., description="净收益（元）")
    net_return: float = Field(..., description="净收益率（%）")
    action: str = Field(..., description="操作动作：buy买入/sell卖出/hold持有")
    action_level: str = Field(..., description="操作等级：strong_buy强烈买入/buy买入/hold持有/danger危险")
    action_color: str = Field(..., description="操作颜色代码，用于UI显示")
    action_label: str = Field(..., description="操作标签文字")
    principal: float = Field(..., description="本金（元）")
    cost_breakdown: TradeCostDetail = Field(..., description="交易成本明细")


class CashOpportunityResponse(BaseModel):
    """现金机会成本响应 v15"""
    principal: float = Field(..., description="本金（元）")
    days: int = Field(..., description="持有天数")
    daily_cost_rate: float = Field(..., description="每日机会成本率（%）")
    opportunity_cost: float = Field(..., description="机会成本（元）")
    equivalent_cp_loss: float = Field(..., description="等效战力损失")
    hint: str = Field(..., description="提示信息")


class FactorDetail(BaseModel):
    """战力因子详情"""
    name: str = Field(..., description="因子名称")
    weight: str = Field(..., description="因子权重（%），各因子权重之和为100%")
    raw_score: float = Field(..., description="原始得分（0-100）")
    contribution: float = Field(..., description="对总战力的贡献值")
    detail: str = Field(..., description="因子详细说明")


class RiskDetail(BaseModel):
    """风险详情"""
    score: float = Field(..., description="风险评分（0-100）")
    level: str = Field(..., description="风险等级：low低/medium中/high高")
    items: List[str] = Field(..., description="风险项列表")
    adjustment: str = Field(..., description="风险调整说明")


class CPExplanationResponse(BaseModel):
    """战力分解说明 v16"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    total_cp: float = Field(..., description="综合战力评分（0-100）")
    factors: List[Dict[str, Any]] = Field(..., description="各因子得分详情列表")
    risk: RiskDetail = Field(..., description="风险详情")
    data_quality: str = Field(..., description="数据质量：high/medium/low")
    summary: str = Field(..., description="战力评估总结")


class HoldingItem(BaseModel):
    """持仓项"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    quantity: int = Field(..., description="持股数量（股），必须是100的整数倍")
    cost_price: float = Field(..., description="成本价（元）")


class HoldingsImportRequest(BaseModel):
    """持仓导入请求"""
    holdings: List[HoldingItem] = Field(..., description="持仓列表")


class HoldingsExportResponse(BaseModel):
    """持仓导出响应"""
    holdings: List[HoldingItem] = Field(..., description="持仓列表")
    total_count: int = Field(..., description="持仓股票数量")
    export_time: str = Field(..., description="导出时间，ISO格式")


class UserProfile(BaseModel):
    """用户约束配置"""
    capital: float = Field(default=20000, description="资金量（元），默认2万")
    allowed_boards: List[str] = Field(default=['main'], description="允许交易的板块列表：main主板/gem创业板/star科创板/bge北交所")
    risk_preference: str = Field(default='aggressive', description="风险偏好：conservative保守/balanced平衡/aggressive激进")
    consider_dividend: bool = Field(default=True, description="是否考虑股息因素")
    keep_cash_reserve: bool = Field(default=False, description="是否预留现金（10%）")
    created_at: Optional[str] = Field(None, description="创建时间，ISO格式")
    updated_at: Optional[str] = Field(None, description="更新时间，ISO格式")


class UserProfileResponse(BaseModel):
    """用户配置响应"""
    profile: UserProfile = Field(..., description="用户配置信息")
    affordable_stocks_count: int = Field(default=0, description="当前资金可购买的股票种数")
    filter_summary: str = Field(default="", description="筛选条件说明文字")


# ==================== 模拟交易相关模型 ====================

class AccountResponse(BaseModel):
    """账户摘要"""
    cash: float = Field(..., description="可用资金（元）")
    initial_cash: float = Field(..., description="初始资金（元）")
    total_market_value: float = Field(default=0, description="持仓总市值（元）")
    total_assets: float = Field(default=0, description="总资产（元）= 现金 + 市值")
    total_profit: float = Field(default=0, description="总盈亏金额（元），正数为盈利")
    profit_rate: float = Field(default=0, description="盈亏比例（%），相对于初始资金")


class HoldingDetail(BaseModel):
    """持仓明细（含实时价格和盈亏）"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    quantity: int = Field(..., description="持股数量（股）")
    cost_price: float = Field(..., description="成本价（元）")
    current_price: float = Field(default=0, description="当前价（元）")
    market_value: float = Field(default=0, description="市值（元）= 数量 × 当前价")
    profit: float = Field(default=0, description="盈亏金额（元），正数为盈利")
    profit_rate: float = Field(default=0, description="盈亏比例（%）")
    bought_at: str = Field(default="", description="最新买入时间，ISO格式")
    can_sell: int = Field(default=0, description="可卖出数量（股），不含今日买入部分")
    on_cooldown: bool = Field(default=False, description="是否在交易冷却期内（创业板等有买入后第二个交易日才能卖出的限制）")
    cooldown_days_remaining: int = Field(default=0, description="冷却期剩余天数")


class PortfolioResponse(BaseModel):
    """持仓明细响应"""
    holdings: List[HoldingDetail] = Field(..., description="持仓列表")
    total_market_value: float = Field(..., description="持仓总市值（元）")
    total_profit: float = Field(..., description="持仓总盈亏（元）")
    cash: float = Field(..., description="可用资金（元）")
    total_assets: float = Field(..., description="总资产（元）")


class TradeRequest(BaseModel):
    """交易请求"""
    code: str = Field(..., description="股票代码")
    quantity: int = Field(..., description="买卖数量（股），必须是100的整数倍")
    order_type: str = Field(default="market", description="下单类型: market=市价, limit=限价")
    price: Optional[float] = Field(default=None, description="限价价格（order_type=limit时必填）")

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v):
        if v <= 0:
            raise ValueError('数量必须大于0')
        if v % 100 != 0:
            raise ValueError('数量必须是100的整数倍（1手）')
        return v


class TradeCostBreakdown(BaseModel):
    """交易成本明细"""
    commission: float = Field(..., description="佣金（元），通常为成交额的0.03%-0.05%")
    stamp_tax: float = Field(..., description="印花税（元），仅卖出时收取，成交额的0.1%")
    transfer_fee: float = Field(..., description="过户费（元），成交额的0.002%")
    total_cost: float = Field(..., description="总交易成本（元）")


class TradeResponse(BaseModel):
    """交易响应"""
    success: bool = Field(..., description="交易是否成功")
    action: str = Field(..., description="交易动作：buy买入/sell卖出")
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    quantity: int = Field(..., description="成交数量（股）")
    price: float = Field(..., description="成交价格（元）")
    total_amount: float = Field(..., description="成交金额（元）= 数量 × 价格")
    cost_detail: TradeCostBreakdown = Field(..., description="交易成本明细")
    cash_after: float = Field(..., description="交易后可用资金（元）")
    message: str = Field(default="", description="交易结果消息或错误说明")


class TradeHistoryItem(BaseModel):
    """交易历史项"""
    id: int = Field(..., description="交易记录ID")
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    action: str = Field(..., description="交易动作：buy买入/sell卖出")
    quantity: int = Field(..., description="成交数量（股）")
    price: float = Field(..., description="成交价格（元）")
    commission: float = Field(..., description="佣金（元）")
    stamp_tax: float = Field(..., description="印花税（元），仅卖出时收取")
    transfer_fee: float = Field(..., description="过户费（元）")
    total_amount: float = Field(..., description="成交金额（元）")
    recorded_at: str = Field(..., description="记录时间，ISO格式")


class TradeHistoryResponse(BaseModel):
    """交易历史响应"""
    trades: List[TradeHistoryItem] = Field(..., description="交易历史列表")
    total_count: int = Field(..., description="交易记录总数")


# ==================== 预测引擎Schema ====================

class GainPredictionItem(BaseModel):
    """涨幅预测项"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    predicted_gain_3d: float = Field(..., description="预测3日涨幅（%），正值表示预计上涨")
    predicted_gain_5d: float = Field(..., description="预测5日涨幅（%），正值表示预计上涨")
    confidence: float = Field(..., description="置信度（0-1），越高预测越可靠")
    confidence_interval_3d: List[float] = Field(..., description="3日预测置信区间 [最低, 最高]")
    confidence_interval_5d: List[float] = Field(..., description="5日预测置信区间 [最低, 最高]")
    features: Dict[str, float] = Field(..., description="主要特征值，用于预测的技术指标")
    model_version: str = Field(default="rule_v19.8", description="预测模型版本")


class GainPredictionResponse(BaseModel):
    """涨幅预测响应"""
    predictions: List[GainPredictionItem] = Field(..., description="预测列表")
    calculated_at: str = Field(..., description="预测计算时间，ISO格式")
    data_timestamp: str = Field(..., description="数据时间戳")
    stock_count: int = Field(..., description="预测股票数量")
    distribution: Dict[str, float] = Field(..., description="预测分布统计，如各涨跌幅区间的股票数量")
    avg_confidence: float = Field(..., description="平均置信度（0-1）")


class ProbabilityPredictionItem(BaseModel):
    """上涨概率预测项"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    up_probability_3d: float = Field(..., description="3日上涨概率（0-1），>0.5表示看涨")
    up_probability_5d: float = Field(..., description="5日上涨概率（0-1），>0.5表示看涨")
    confidence: float = Field(..., description="置信度（0-1），越高预测越可靠")
    risk_level: str = Field(default='low', description="风险等级：low/medium/high")
    features: Dict[str, float] = Field(..., description="主要特征值，用于预测的技术指标")
    model_version: str = Field(default="rule_v19.8", description="预测模型版本")


class ProbabilityPredictionResponse(BaseModel):
    """上涨概率预测响应"""
    predictions: List[ProbabilityPredictionItem] = Field(..., description="预测列表")
    calculated_at: str = Field(..., description="预测计算时间，ISO格式")
    data_timestamp: str = Field(..., description="数据时间戳")
    stock_count: int = Field(..., description="预测股票数量")


# ==================== 完整回测Schema ====================

class BacktestTradeResponse(BaseModel):
    """回测交易记录"""
    date: str = Field(..., description="交易日期，YYYY-MM-DD格式")
    action: str = Field(..., description="交易动作：buy买入/sell卖出")
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    price: float = Field(..., description="成交价格（元）")
    quantity: int = Field(..., description="成交数量（股）")
    amount: float = Field(..., description="成交金额（元）")
    commission: float = Field(..., description="佣金（元）")
    profit: float = Field(default=0.0, description="平仓盈亏（元）")
    reason: str = Field(default="", description="交易原因说明")


class EquityPointResponse(BaseModel):
    """净值曲线数据点"""
    date: str = Field(..., description="日期，YYYY-MM-DD格式")
    total_value: float = Field(..., description="总资产（元）")
    cash: float = Field(..., description="现金余额（元）")
    position_value: float = Field(..., description="持仓市值（元）")


class FullBacktestResponse(BaseModel):
    """完整回测响应"""
    start_date: str = Field(..., description="回测开始日期，YYYY-MM-DD格式")
    end_date: str = Field(..., description="回测结束日期，YYYY-MM-DD格式")
    strategy: str = Field(..., description="策略名称")
    top_n: int = Field(..., description="持仓股票数量上限")
    initial_capital: float = Field(..., description="初始资金（元）")
    final_value: float = Field(..., description="最终资产（元）")
    total_return: float = Field(..., description="总收益率（%），相对于初始资金")
    annualized_return: float = Field(..., description="年化收益率（%）")
    sharpe_ratio: float = Field(..., description="夏普比率，衡量风险调整后的收益")
    max_drawdown: float = Field(..., description="最大回撤（%），历史最大亏损幅度")
    win_rate: float = Field(..., description="胜率（%），盈利交易次数/总交易次数")
    total_trades: int = Field(..., description="总交易次数")
    equity_curve: List[EquityPointResponse] = Field(..., description="每日净值曲线")
    trades: List[BacktestTradeResponse] = Field(..., description="交易记录列表")
    completed_pnls: List[float] = Field(default_factory=list, description="已平仓交易的盈亏列表（元）")
