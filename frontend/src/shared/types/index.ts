// API Types

// 战力数据 (匹配 backend SingleStockResponse)
export interface StockCP {
  code: string
  name: string
  price: number
  change_pct: number  // 涨跌幅 (%)
  total_cp: number
  growth_score: number  // 成长分
  value_score: number  // 价值分
  quality_score: number  // 质量分
  momentum_score: number  // 动量分
  risk_score?: number
  risk_level?: string
  pe?: number
  pb?: number
  gross_margin?: number
  revenue?: number
  cashflow?: number
  debt_ratio?: number
  dividend_yield?: number
  market_cap?: number
  high?: number  // 最高价
  low?: number  // 最低价
  data_quality?: 'high' | 'medium' | 'low'
  board_type?: string
  board_name?: string
  can_trade_newbie?: boolean
  trade_requirement?: string
  sector?: string
  momentum_3d?: number
  momentum_5d?: number
  current_ratio?: number
  interest_coverage?: number
  deducted_net_profit?: number
  // 兼容字段别名
  change?: number  // change_pct alias
  changePercent?: number  // change_pct alias
  growth_cp?: number  // growth_score alias
  value_cp?: number  // value_score alias
  quality_cp?: number  // quality_score alias
  momentum_cp?: number  // momentum_score alias
  high_price?: number  // high alias
  low_price?: number  // low alias
}

export interface CPTopResponse {
  data: StockCP[]
  updated_at: string
  total: number
}

export interface StockDetail {
  code: string
  name: string
  price: number
  change_pct: number  // 涨跌幅 (%)
  total_cp: number
  growth_score: number
  value_score: number
  quality_score: number
  momentum_score: number
  risk_score?: number
  risk_level?: string
  pe?: number
  pb?: number
  gross_margin?: number
  revenue?: number
  cashflow?: number
  debt_ratio?: number
  dividend_yield?: number
  market_cap?: number
  high?: number
  low?: number
  data_quality?: 'high' | 'medium' | 'low'
  board_type?: string
  board_name?: string
  can_trade_newbie?: boolean
  trade_requirement?: string
  sector?: string
  momentum_3d?: number
  momentum_5d?: number
  current_ratio?: number
  interest_coverage?: number
  deducted_net_profit?: number
  // 兼容字段别名
  change?: number
  changePercent?: number
  growth_cp?: number
  value_cp?: number
  quality_cp?: number
  momentum_cp?: number
  high_price?: number
  low_price?: number
  // 财务数据
  revenue_growth?: number
  net_profit_growth?: number
  roe?: number
}

export interface HoldingDetail {
  code: string
  name: string
  quantity: number
  cost_price: number
  current_price: number
  market_value: number
  profit: number
  profit_rate: number
  bought_at: string
  can_sell: number
  on_cooldown: boolean
  cooldown_days_remaining: number
}

export interface AccountResponse {
  cash: number
  initial_cash: number
  total_market_value: number
  total_assets: number
  total_profit: number
  profit_rate: number
}

export interface PortfolioResponse {
  holdings: HoldingDetail[]
  total_market_value: number
  total_profit: number
  cash: number
  total_assets: number
}

export interface TradeCostBreakdown {
  commission: number
  stamp_tax: number
  transfer_fee: number
  total_cost: number
}

export interface TradeResult {
  success: boolean
  action: 'buy' | 'sell'
  code: string
  name: string
  quantity: number
  price: number
  total_amount: number
  cost_detail: TradeCostBreakdown
  cash_after: number
  message: string
}

export interface TradeHistoryItem {
  id: number
  code: string
  name: string
  action: 'buy' | 'sell'
  quantity: number
  price: number
  commission: number
  stamp_tax: number
  transfer_fee: number
  total_amount: number
  recorded_at: string
}

export interface TradeHistoryResponse {
  trades: TradeHistoryItem[]
  total_count: number
}

export interface TradeResult {
  success: boolean
  message: string
  trade_id?: string
  price?: number
  shares?: number
  amount?: number
  commission?: number
}

export interface SwapSuggestion {
  from_code: string
  from_name: string
  from_cp: number
  to_code: string
  to_name: string
  to_cp: number
  cp_improvement: number
  trade_cost: number
  net_benefit: number
  holding_days_equivalent: number
  action_level: string
  action_label: string
}

export interface RecommendResponse {
  category: string
  total: number
  data: StockCP[]
  swap_suggestions: SwapSuggestion[]
  portfolio_diversity: Record<string, number>
  filters_applied: Record<string, unknown>
  risk_preference: string
  error?: string
}

export interface BacktestParams {
  start_date: string
  end_date: string
  holding_days?: number
  top_n?: number
}

export interface BacktestResult {
  total_return?: number
  annual_return?: number
  sharpe_ratio?: number
  max_drawdown?: number
  win_rate?: number
  total_trades?: number
  monthly_returns?: Array<{ month: string; return: number }>
  // 回测结果可能包含更多字段
  [key: string]: unknown
}

export interface MarketStats {
  total_stocks: number
  up_count: number
  down_count: number
  flat_count: number
  limit_up_count: number
  limit_down_count: number
  total_amount: number
  market_capitalization: number
}

export interface WatchlistGroup {
  id: string
  name: string
  codes: string[]
  color?: string
}

// WebSocket Message Types
export type WSMessageType = 'quote' | 'kline' | 'trade' | 'depth'

export interface WSMessage {
  type: WSMessageType
  data: unknown
}

export interface QuoteUpdate {
  code: string
  price: number
  change: number
  changePercent: number
  volume: number
  timestamp: number
}

// ==================== 预测分析模块 (v19.8) ====================

export interface GainPrediction {
  code: string
  name: string
  predicted_gain_3d: number
  predicted_gain_5d: number
  confidence: number
  confidence_interval_3d: [number, number]
  confidence_interval_5d: [number, number]
  features: Record<string, number>
  model_version: string
}

export interface ProbabilityPrediction {
  code: string
  name: string
  up_probability_3d: number
  up_probability_5d: number
  confidence: number
  risk_level: 'low' | 'medium' | 'high'
  features: Record<string, number>
  model_version: string
}

export interface GainPredictionItem extends GainPrediction {
  rank?: number
}

export interface ProbabilityPredictionItem extends ProbabilityPrediction {
  rank?: number
}

export interface GainPredictionResponse {
  predictions: GainPrediction[]
  calculated_at: string
  data_timestamp: string
  stock_count: number
  distribution: Record<string, number>
  avg_confidence: number
}

export interface ProbabilityPredictionResponse {
  predictions: ProbabilityPrediction[]
  calculated_at: string
  data_timestamp: string
  stock_count: number
}

// ==================== 验证报告模块 (v19.8) ====================

export interface SwapVerification {
  total_swaps: number
  profitable_count: number
  avg_profit_pct: number
  total_profit: number
  win_rate: number
}

export interface CPPredictionAccuracy {
  period: string
  total_stocks: number
  high_cp_group_avg_profit: number
  low_cp_group_avg_profit: number
  high_cp_beats_market_rate: number
  high_cp_vs_market: number
  low_cp_vs_market: number
}

export interface GainPredictionAccuracy {
  period: string
  total_stocks: number
  avg_predicted_gain: number
  avg_actual_gain: number
  prediction_error: number
  mean_absolute_error: number
  accuracy_direction: number
  top_predicted_avg: number
}

export interface ProbabilityPredictionAccuracy {
  period: string
  total_stocks: number
  high_prob_avg_actual: number
  low_prob_avg_actual: number
  calibration_error: number
  direction_accuracy: number
  high_prob_accuracy: number
  low_prob_accuracy: number
}

export interface VerifyReport {
  report_date: string
  swap_verification: SwapVerification
  cp_prediction_accuracy: CPPredictionAccuracy
  gain_prediction_accuracy?: GainPredictionAccuracy
  probability_prediction_accuracy?: ProbabilityPredictionAccuracy
  conclusion: string
}

// ==================== 用户配置 ====================

export interface UserProfile {
  capital: number
  allowed_boards: string[]
  risk_preference: string
  consider_dividend: boolean
  keep_cash_reserve: boolean
  created_at: string | null
  updated_at: string | null
}

export interface UserProfileResponse {
  profile: UserProfile
  affordable_stocks_count: number
  filter_summary: string
}

// ==================== 健康检查 ====================

export interface HealthResponse {
  status: 'ok' | 'error'
  timestamp: string
  data_fresh: boolean
  last_update: string
  stocks_count: number
}

// ==================== 风险报告 ====================

export interface RiskReport {
  report_date: string
  total_exposed: number
  avg_risk_score: number
  high_risk_count: number
  positions_at_risk: Array<{
    code: string
    name: string
    risk_score: number
    potential_loss: number
  }>
  recommendations: string[]
}
